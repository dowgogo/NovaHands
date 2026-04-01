"""
观察编码器模块

将桌面环境观察编码为潜在向量。

支持多模态输入：
- 屏幕截图（图像）
- 窗口标题（文本）
- 活动应用（文本）
- 光标位置（坐标）
- 文件状态变化（文本列表）

设计原则：
- 轻量级（避免 GPU 依赖）
- 可缓存（提升推理速度）
- 可扩展（易于添加新的观察类型）
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, Tuple, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import hashlib
import pickle
import string

logger = logging.getLogger("novahands")


@dataclass
class EncoderConfig:
    """编码器配置"""
    # 屏幕编码
    screen_size: Tuple[int, int] = (64, 64)  # 下采样尺寸
    screen_channels: int = 3  # RGB 通道
    screen_feature_dim: int = 64  # 屏幕特征维度
    
    # 文本编码
    text_embedding_dim: int = 32  # 文本嵌入维度
    max_text_length: int = 64  # 最大文本长度
    
    # 坐标编码
    position_embedding_dim: int = 16  # 位置嵌入维度
    
    # 融合层
    latent_dim: int = 128  # 最终潜在维度
    hidden_dim: int = 256  # 隐藏层维度
    
    # 缓存
    cache_encodings: bool = True  # 是否缓存编码结果
    cache_size: int = 1000  # 缓存大小


class BaseObservationEncoder(ABC):
    """
    观察编码器基类
    
    定义编码器接口，便于扩展和替换
    """
    
    @abstractmethod
    def encode(self, observation: Dict[str, Any]) -> np.ndarray:
        """
        编码单个观察
        
        Parameters
        ----------
        observation : dict
            观察数据，包含：
            - screenshot: np.ndarray (H, W, 3) 屏幕截图
            - window_title: str 窗口标题
            - active_app: str 活动应用名称
            - cursor_pos: (x, y) 光标位置
            - file_changes: List[str] 文件变化列表
            
        Returns
        -------
        latent_vector : np.ndarray (latent_dim,)
            编码后的潜在向量
        """
        pass
    
    @abstractmethod
    def encode_batch(
        self,
        observations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        批量编码
        
        Parameters
        ----------
        observations : list of dict
            观察列表
            
        Returns
        -------
        latent_vectors : np.ndarray (batch_size, latent_dim)
        """
        pass
    
    def get_config(self) -> EncoderConfig:
        """获取配置"""
        raise NotImplementedError


class SimpleObservationEncoder(BaseObservationEncoder):
    """
    简单观察编码器（无神经网络依赖）
    
    特点：
    - 纯 numpy 实现，无需 GPU
    - 轻量级，适合资源受限环境
    - 可扩展，易于添加新特征
    """
    
    def __init__(self, config: Optional[EncoderConfig] = None):
        """
        Parameters
        ----------
        config : EncoderConfig, optional
            编码器配置（默认使用默认配置）
        """
        self.config = config or EncoderConfig()
        
        # 编码缓存
        self._cache = {} if self.config.cache_encodings else None
        
        # 初始化文本嵌入哈希表
        self._text_embeddings = {}
        
        # 特征维度计算
        self._total_feature_dim = (
            self.config.screen_feature_dim +
            self.config.text_embedding_dim * 2 +  # window_title + active_app
            self.config.position_embedding_dim
        )
        
        logger.info(
            f"SimpleObservationEncoder initialized: "
            f"latent_dim={self.config.latent_dim}, "
            f"feature_dim={self._total_feature_dim}"
        )
    
    def _hash_observation(self, observation: Dict[str, Any]) -> str:
        """
        计算观察的哈希值（用于缓存）
        """
        # 提取关键信息
        key_data = {
            "window_title": observation.get("window_title", ""),
            "active_app": observation.get("active_app", ""),
            "cursor_pos": observation.get("cursor_pos", (0, 0)),
            # 屏幕截图不参与哈希（太大）
        }
        
        key_str = str(sorted(key_data.items()))
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _encode_screen(
        self,
        screenshot: Optional[np.ndarray]
    ) -> np.ndarray:
        """
        编码屏幕截图
        
        Parameters
        ----------
        screenshot : np.ndarray (H, W, 3) or None
            屏幕截图
            
        Returns
        -------
        screen_features : np.ndarray (screen_feature_dim,)
        """
        if screenshot is None:
            return np.zeros(self.config.screen_feature_dim)
        
        # 下采样
        try:
            from scipy.ndimage import zoom
            h, w = screenshot.shape[:2]
            scale_factors = (
                self.config.screen_size[0] / h,
                self.config.screen_size[1] / w,
                1
            )
            resized = zoom(screenshot, scale_factors, order=1)
        except ImportError:
            # 回退：使用 numpy 重采样
            resized = self._simple_resize(screenshot, self.config.screen_size)
        
        # 简单特征提取：RGB 通道均值和标准差
        features = []
        
        # 每个通道的均值和标准差
        for channel in range(3):
            channel_data = resized[:, :, channel]
            features.append(np.mean(channel_data))
            features.append(np.std(channel_data))
        
        # 空间分布：4 个象限的均值
        h, w = resized.shape[:2]
        quadrants = [
            resized[:h//2, :w//2],
            resized[:h//2, w//2:],
            resized[h//2:, :w//2],
            resized[h//2:, w//2:]
        ]
        for quad in quadrants:
            features.append(np.mean(quad))
        
        # 边缘密度（梯度）
        gradient_h = np.abs(np.diff(resized, axis=0)).mean()
        gradient_v = np.abs(np.diff(resized, axis=1)).mean()
        features.append(gradient_h)
        features.append(gradient_v)
        
        # 填充或截断到目标维度
        features = np.array(features, dtype=np.float32)
        
        if len(features) < self.config.screen_feature_dim:
            # 填充零
            features = np.pad(
                features,
                (0, self.config.screen_feature_dim - len(features)),
                mode='constant'
            )
        elif len(features) > self.config.screen_feature_dim:
            # 截断
            features = features[:self.config.screen_feature_dim]
        
        return features
    
    def _simple_resize(
        self,
        image: np.ndarray,
        target_size: Tuple[int, int]
    ) -> np.ndarray:
        """
        简单图像重采样（无 scipy 依赖）
        """
        h, w = image.shape[:2]
        th, tw = target_size
        
        # 计算采样索引
        indices_h = (np.arange(th) * (h / th)).astype(int)
        indices_w = (np.arange(tw) * (w / tw)).astype(int)
        
        if len(image.shape) == 3:
            resized = image[np.ix_(indices_h, indices_w, [0, 1, 2])]
        else:
            resized = image[np.ix_(indices_h, indices_w)]
        
        return resized
    
    def _encode_text(
        self,
        text: str
    ) -> np.ndarray:
        """
        编码文本（基于字符统计）
        
        Parameters
        ----------
        text : str
            文本字符串
            
        Returns
        -------
        text_embedding : np.ndarray (text_embedding_dim,)
        """
        if not text:
            return np.zeros(self.config.text_embedding_dim)
        
        # 检查缓存
        if text in self._text_embeddings:
            return self._text_embeddings[text]
        
        # 简单特征：字符统计
        features = []
        
        # 字符类别统计
        features.append(len([c for c in text if c.isupper()]))  # 大写
        features.append(len([c for c in text if c.islower()]))  # 小写
        features.append(len([c for c in text if c.isdigit()]))  # 数字
        features.append(len([c for c in text if c in " \t\n"]))  # 空白
        features.append(len([c for c in text if c in string.punctuation]))  # 标点
        features.append(len(text))  # 总长度
        
        # 唯一字符数
        features.append(len(set(text)))
        
        # 首字符和尾字符的 ASCII 码
        if text:
            features.append(ord(text[0]) / 256.0)
            features.append(ord(text[-1]) / 256.0)
        else:
            features.extend([0.0, 0.0])
        
        # 填充或截断
        features = np.array(features, dtype=np.float32)
        
        if len(features) < self.config.text_embedding_dim:
            features = np.pad(
                features,
                (0, self.config.text_embedding_dim - len(features)),
                mode='constant'
            )
        elif len(features) > self.config.text_embedding_dim:
            features = features[:self.config.text_embedding_dim]
        
        # 归一化
        features = features / (np.linalg.norm(features) + 1e-8)
        
        # 缓存
        if len(self._text_embeddings) < 10000:  # 限制缓存大小
            self._text_embeddings[text] = features
        
        return features
    
    def _encode_position(
        self,
        pos: Tuple[int, int],
        screen_size: Tuple[int, int] = (1920, 1080)
    ) -> np.ndarray:
        """
        编码光标位置
        
        Parameters
        ----------
        pos : (x, y)
            光标坐标
        screen_size : (width, height)
            屏幕尺寸（用于归一化）
            
        Returns
        -------
        position_embedding : np.ndarray (position_embedding_dim,)
        """
        x, y = pos
        width, height = screen_size
        
        # 归一化到 [0, 1]
        norm_x = x / width
        norm_y = y / height
        
        # 简单嵌入：归一化坐标 + 距离中心的归一化距离
        center_x, center_y = width / 2, height / 2
        dist_center = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        norm_dist = dist_center / max_dist
        
        # 扩展到目标维度
        features = np.array([norm_x, norm_y, norm_dist], dtype=np.float32)
        
        if len(features) < self.config.position_embedding_dim:
            features = np.pad(
                features,
                (0, self.config.position_embedding_dim - len(features)),
                mode='constant'
            )
        elif len(features) > self.config.position_embedding_dim:
            features = features[:self.config.position_embedding_dim]
        
        return features
    
    def encode(self, observation: Dict[str, Any]) -> np.ndarray:
        """
        编码单个观察
        """
        # 检查缓存
        if self._cache is not None:
            cache_key = self._hash_observation(observation)
            if cache_key in self._cache:
                return self._cache[cache_key]
        
        # 提取观察组件
        screenshot = observation.get("screenshot")
        window_title = observation.get("window_title", "")
        active_app = observation.get("active_app", "")
        cursor_pos = observation.get("cursor_pos", (0, 0))
        
        # 编码各组件
        screen_features = self._encode_screen(screenshot)
        title_features = self._encode_text(window_title)
        app_features = self._encode_text(active_app)
        position_features = self._encode_position(cursor_pos)
        
        # 拼接特征
        combined = np.concatenate([
            screen_features,
            title_features,
            app_features,
            position_features
        ])
        
        # 投影到潜在维度（简单的线性变换 + 非线性）
        # W: (latent_dim, total_feature_dim), b: (latent_dim,)
        W = np.random.randn(
            self.config.latent_dim,
            len(combined)
        ) * 0.01
        b = np.zeros(self.config.latent_dim)
        
        latent = np.dot(W, combined) + b
        latent = np.tanh(latent)  # 非线性激活
        
        # 归一化
        latent = latent / (np.linalg.norm(latent) + 1e-8)
        
        # 缓存
        if self._cache is not None:
            if len(self._cache) >= self.config.cache_size:
                # 移除最旧的缓存
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = latent
        
        return latent
    
    def encode_batch(
        self,
        observations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """
        批量编码
        """
        return np.array([self.encode(obs) for obs in observations])
    
    def get_config(self) -> EncoderConfig:
        """获取配置"""
        return self.config
    
    def save_cache(self, filepath: str):
        """保存编码缓存"""
        if self._cache is None:
            return
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "wb") as f:
            pickle.dump({
                "cache": self._cache,
                "text_embeddings": self._text_embeddings
            }, f)
        
        logger.info(f"Encoder cache saved to {filepath}")
    
    def load_cache(self, filepath: str):
        """加载编码缓存"""
        if not self.config.cache_encodings:
            return
        
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Cache file not found: {filepath}")
            return
        
        with open(path, "rb") as f:
            data = pickle.load(f)
            self._cache = data.get("cache", {})
            self._text_embeddings = data.get("text_embeddings", {})
        
        logger.info(f"Encoder cache loaded from {filepath}")


def create_encoder(
    encoder_type: str = "simple",
    config: Optional[EncoderConfig] = None
) -> BaseObservationEncoder:
    """
    工厂函数：创建编码器
    
    Parameters
    ----------
    encoder_type : str
        编码器类型（"simple", "cnn", "transformer"）
    config : EncoderConfig, optional
        配置对象
        
    Returns
    -------
    encoder : BaseObservationEncoder
        编码器实例
    """
    if encoder_type == "simple":
        return SimpleObservationEncoder(config)
    else:
        raise ValueError(f"Unknown encoder type: {encoder_type}")


# 导入 string 模块
import string
