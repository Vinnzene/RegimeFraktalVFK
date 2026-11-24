"""Arsitektur 3 model pembanding."""

from __future__ import annotations

from typing import Tuple

import tensorflow as tf  # type: ignore
layers = tf.keras.layers
models = tf.keras.models


@tf.keras.utils.register_keras_serializable(package="regimefraktal")
class AttentionPooling(layers.Layer):
    """Additive attention (Bahdanau) atas dimensi waktu."""

    def __init__(self, units: int = 64, **kwargs) -> None:
        super().__init__(**kwargs)
        self.units = units
        self.score_dense = layers.Dense(units, activation="tanh")
        self.score_vector = layers.Dense(1, use_bias=False)

    def call(self, inputs):
        score = self.score_vector(self.score_dense(inputs))  # (B, T, 1)
        weights = tf.nn.softmax(score, axis=1)
        context = tf.reduce_sum(weights * inputs, axis=1)
        self.last_attention = tf.squeeze(weights, axis=-1)
        return context

    def compute_attention(self, inputs):
        score = self.score_vector(self.score_dense(inputs))
        return tf.squeeze(tf.nn.softmax(score, axis=1), axis=-1)

    def get_config(self) -> dict:
        return {**super().get_config(), "units": self.units}


def build_swt_bilstm(
    input_shape: Tuple[int, int],
    n_classes: int = 3,
    lstm_units: int = 64,
    dropout: float = 0.2,
) -> models.Model:
    """Baseline 2: tanpa attention. Memakai state akhir BiLSTM."""
    inp = layers.Input(shape=input_shape, name="swt_features")
    x = layers.Bidirectional(layers.LSTM(lstm_units, return_sequences=True))(inp)
    x = layers.Dropout(dropout)(x)
    x = layers.Bidirectional(layers.LSTM(lstm_units // 2))(x)
    x = layers.Dropout(dropout)(x)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(x)
    return models.Model(inp, out, name="swt_bilstm")


def build_swt_attention_bilstm(
    input_shape: Tuple[int, int],
    n_classes: int = 3,
    lstm_units: int = 64,
    dropout: float = 0.2,
) -> models.Model:
    """Model usulan skripsi: BiLSTM + attention pooling."""
    inp = layers.Input(shape=input_shape, name="swt_features")
    seq = layers.Bidirectional(layers.LSTM(lstm_units, return_sequences=True))(inp)
    seq = layers.Dropout(dropout)(seq)
    context = AttentionPooling(units=lstm_units, name="attention_pool")(seq)
    context = layers.Dropout(dropout)(context)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(context)
    return models.Model(inp, out, name="swt_attention_bilstm")


def build_multitask_attention_bilstm(
    input_shape: Tuple[int, int],
    n_classes: int = 3,
    lstm_units: int = 64,
    dropout: float = 0.2,
) -> models.Model:
    """Model usulan dengan DUA head — flow.md langkah 6."""
    inp = layers.Input(shape=input_shape, name="swt_features")
    seq = layers.Bidirectional(layers.LSTM(lstm_units, return_sequences=True))(inp)
    seq = layers.Dropout(dropout)(seq)
    context = AttentionPooling(units=lstm_units, name="attention_pool")(seq)
    context = layers.Dropout(dropout)(context)

    regime = layers.Dense(n_classes, activation="softmax", name="regime")(context)
    hurst = layers.Dense(1, activation="sigmoid", name="hurst")(context)

    return models.Model(inp, [regime, hurst], name="multitask_attention_bilstm")


def build_hybrid_attention_bilstm(
    input_shape: Tuple[int, int],
    n_features: int,
    n_classes: int = 3,
    lstm_units: int = 64,
    dropout: float = 0.25,
    l2_reg: float = 0.0,
) -> models.Model:
    """SWT + Attention-BiLSTM digabung dengan fitur struktural."""
    reg = tf.keras.regularizers.l2(l2_reg) if l2_reg > 0 else None

    seq_in = layers.Input(shape=input_shape, name="swt_features")
    feat_in = layers.Input(shape=(n_features,), name="structural_features")

    seq = layers.Bidirectional(
        layers.LSTM(lstm_units, return_sequences=True, kernel_regularizer=reg, recurrent_regularizer=reg)
    )(seq_in)
    seq = layers.Dropout(dropout)(seq)
    context = AttentionPooling(units=lstm_units, name="attention_pool")(seq)

    feat = layers.Dense(64, activation="relu", kernel_regularizer=reg)(feat_in)
    feat = layers.Dropout(dropout)(feat)
    feat = layers.Dense(32, activation="relu", kernel_regularizer=reg)(feat)

    merged = layers.Concatenate()([context, feat])
    merged = layers.Dropout(dropout)(merged)
    merged = layers.Dense(64, activation="relu", kernel_regularizer=reg)(merged)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(merged)

    return models.Model([seq_in, feat_in], out, name="hybrid_attention_bilstm")


def build_adaptive_hybrid_attention_bilstm(
    input_shape: Tuple[int, int],
    n_features: int,
    n_classes: int = 3,
    timeframe: str = "1h",
    l2_reg: float = 1e-4,
) -> models.Model:
    """Arsitektur Hybrid adaptif per timeframe untuk mencapai Generalization Sweet Spot."""
    is_4h = timeframe.lower() == "4h"
    lstm_units = 24 if is_4h else 64
    d1 = 32 if is_4h else 64
    d2 = 16 if is_4h else 32
    d3 = 32 if is_4h else 64
    dropout = 0.35 if is_4h else 0.25
    effective_reg = (l2_reg * 2.0) if is_4h else l2_reg

    reg = tf.keras.regularizers.l2(effective_reg) if effective_reg > 0 else None

    seq_in = layers.Input(shape=input_shape, name="seq_features")
    feat_in = layers.Input(shape=(n_features,), name="structural_features")

    seq = layers.Bidirectional(
        layers.LSTM(lstm_units, return_sequences=True, kernel_regularizer=reg, recurrent_regularizer=reg)
    )(seq_in)
    seq = layers.Dropout(dropout)(seq)
    context = AttentionPooling(units=lstm_units, name="attention_pool")(seq)

    feat = layers.Dense(d1, activation="relu", kernel_regularizer=reg)(feat_in)
    feat = layers.Dropout(dropout)(feat)
    feat = layers.Dense(d2, activation="relu", kernel_regularizer=reg)(feat)

    merged = layers.Concatenate()([context, feat])
    merged = layers.Dropout(dropout)(merged)
    merged = layers.Dense(d3, activation="relu", kernel_regularizer=reg)(merged)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(merged)

    return models.Model([seq_in, feat_in], out, name=f"hybrid_attention_bilstm_{timeframe.lower()}_sweetspot")


def build_orderflow_fusion_model(
    swt_shape: Tuple[int, int],
    orderflow_channels: int,
    n_classes: int = 3,
    lstm_units: int = 64,
    orderflow_units: int = 16,
    dense_units: int = 16,
    dropout: float = 0.2,
) -> models.Model:
    """Eksperimen ablation order flow (Model A–D)."""
    swt_in = layers.Input(shape=swt_shape, name="swt_features")
    seq = layers.Bidirectional(
        layers.LSTM(lstm_units, return_sequences=True), name="swt_bilstm_1"
    )(swt_in)
    seq = layers.Dropout(dropout)(seq)
    seq = layers.Bidirectional(
        layers.LSTM(lstm_units // 2, return_sequences=True), name="swt_bilstm_2"
    )(seq)
    swt_context = AttentionPooling(units=lstm_units // 2, name="attention_pool")(seq)

    inputs = [swt_in]
    merged = swt_context
    if orderflow_channels > 0:
        of_in = layers.Input(shape=(swt_shape[0], orderflow_channels), name="orderflow_features")
        of = layers.Bidirectional(
            layers.LSTM(orderflow_units, return_sequences=True), name="orderflow_bilstm"
        )(of_in)
        of_context = layers.GlobalAveragePooling1D(name="orderflow_context")(of)
        inputs.append(of_in)
        merged = layers.Concatenate(name="fusion")([swt_context, of_context])

    x = layers.Dense(dense_units, activation="relu", name="fusion_dense")(merged)
    x = layers.Dropout(dropout)(x)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(x)
    name = "swt_attn_bilstm_orderflow" if orderflow_channels else "swt_attn_bilstm_base"
    return models.Model(inputs if len(inputs) > 1 else swt_in, out, name=name)


def build_structural_mlp(
    n_features: int,
    n_classes: int = 3,
    dropout: float = 0.25,
) -> models.Model:
    """Pembanding tanpa jalur sekuens — mengukur kontribusi fitur struktural saja."""
    feat_in = layers.Input(shape=(n_features,), name="structural_features")
    x = layers.Dense(128, activation="relu")(feat_in)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(dropout)(x)
    out = layers.Dense(n_classes, activation="softmax", name="regime")(x)
    return models.Model(feat_in, out, name="structural_mlp")


def attention_extractor(model: models.Model) -> models.Model:
    """Model pendamping yang mengeluarkan bobot alpha_t, berbagi bobot terlatih."""
    pool = model.get_layer("attention_pool")
    seq_output = pool.input
    weights = pool.compute_attention(seq_output)
    return models.Model(model.input, weights, name="attention_weights")


def compile_model(
    model: models.Model,
    lr: float = 1e-3,
    label_smoothing: float = 0.0,
) -> models.Model:
    """Compile model dengan opsi label smoothing untuk Generalization Sweet Spot."""
    loss = (
        tf.keras.losses.CategoricalCrossentropy(label_smoothing=label_smoothing)
        if label_smoothing > 0
        else "categorical_crossentropy"
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss=loss,
        metrics=["accuracy"],
    )
    return model


def compile_multitask(
    model: models.Model,
    lr: float = 1e-3,
    lambda_regression: float = 0.3,
) -> models.Model:
    """Loss gabungan: CE(klasifikasi) + lambda * MSE(regresi H)."""
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss={"regime": "categorical_crossentropy", "hurst": "mse"},
        loss_weights={"regime": 1.0, "hurst": lambda_regression},
        metrics={"regime": ["accuracy"], "hurst": ["mae"]},
    )
    return model
