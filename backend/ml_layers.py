"""Lapisan kustom yang dibutuhkan untuk memuat artefak Keras.

Definisi ini harus tersedia di sisi backend karena `tf.keras.models.load_model`
perlu merekonstruksi lapisan non-standar. Ditaruh di tingkat `backend/` agar
paket `app` tidak mengimpor TensorFlow secara tidak sengaja: modul ini hanya
diimpor dari dalam `model_registry.load_model()`, yang memang sudah berada di
jalur yang membutuhkan TF.

Isinya harus identik dengan `ml/src/model_architecture.py`. Perbedaan sekecil
apa pun membuat bobot terlatih dipetakan ke lapisan yang salah.
"""

from __future__ import annotations

import tensorflow as tf  # pyrefly: ignore[untyped-import]  # TensorFlow tidak menyediakan stub tipe

layers = tf.keras.layers


@tf.keras.utils.register_keras_serializable(package="regimefraktal")
class AttentionPooling(layers.Layer):
    """Additive attention (Bahdanau) atas dimensi waktu."""

    def __init__(self, units: int = 64, **kwargs) -> None:
        super().__init__(**kwargs)
        self.units = units
        self.score_dense = layers.Dense(units, activation="tanh")
        self.score_vector = layers.Dense(1, use_bias=False)

    def call(self, inputs):
        score = self.score_vector(self.score_dense(inputs))
        weights = tf.nn.softmax(score, axis=1)
        context = tf.reduce_sum(weights * inputs, axis=1)
        self.last_attention = tf.squeeze(weights, axis=-1)
        return context

    def compute_attention(self, inputs):
        score = self.score_vector(self.score_dense(inputs))
        return tf.squeeze(tf.nn.softmax(score, axis=1), axis=-1)

    def get_config(self) -> dict:
        return {**super().get_config(), "units": self.units}
