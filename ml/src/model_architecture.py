"""Arsitektur 3 model pembanding.

    1. rule_based           — bukan jaringan saraf, lihat evaluate.py
    2. swt_bilstm           — SWT -> BiLSTM -> Dense -> Softmax(3)
    3. swt_attention_bilstm — SWT -> BiLSTM -> Attention -> Dense -> Softmax(3)

Output selalu 3 kelas. Kategori keempat (uncertain_lowconf) lahir di
post-processing lewat threshold tau, bukan dari lapisan softmax — konsisten
dengan Bab 3.3.3 yang mengeluarkan window uncertain_rule dari data training.

Bobot attention diambil lewat model terpisah yang berbagi bobot dengan model
utama (`attention_extractor`), bukan sebagai output kedua saat training. Dengan
begitu loss hanya dihitung pada head regime dan tidak ada head tambahan yang
perlu dipasangkan target palsu.
"""

from __future__ import annotations

from typing import Tuple

import tensorflow as tf  # type: ignore
layers = tf.keras.layers
models = tf.keras.models


@tf.keras.utils.register_keras_serializable(package="regimefraktal")
class AttentionPooling(layers.Layer):
    """Additive attention (Bahdanau) atas dimensi waktu.

    Menghasilkan konteks c = sum_t alpha_t * h_t. Bobot alpha_t disimpan pada
    atribut agar bisa diambil lewat model ekstraktor untuk halaman /attention.
    """

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
    """Model usulan dengan DUA head — flow.md langkah 6.

    Head 1 (`regime`)   : softmax n_classes, target dari labeling Hurst-DFA.
    Head 2 (`hurst`)    : regresi nilai H kontinu, target dari estimasi rolling.

    Alasan head kedua
    -----------------
    Label regime adalah hasil diskretisasi H lewat ambang. Diskretisasi itu
    membuang informasi: window dengan H = 0.56 dan H = 0.85 mendapat label sama
    padahal jaraknya jauh. Head regresi memaksa representasi internal tetap
    membawa besaran kontinu tersebut, sehingga fitur yang dipelajari harus
    monoton terhadap persistensi — bukan sekadar cukup untuk memisahkan tiga
    kotak.

    Keduanya berbagi seluruh badan jaringan; yang berbeda hanya lapisan akhir.
    Itulah inti multi-task: gradien dari tugas regresi ikut membentuk encoder
    yang dipakai tugas klasifikasi.

    Head regresi memakai aktivasi sigmoid karena H terdefinisi pada (0, 1).
    Tanpa pembatasan itu, keluaran dapat melenceng ke nilai yang tidak punya
    arti fisik dan MSE-nya mendominasi loss gabungan di awal training.
    """
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
    """SWT + Attention-BiLSTM digabung dengan fitur struktural.

    Jalur sekuens menangkap pola temporal koefisien wavelet; jalur fitur
    menyuplai ringkasan struktural (variance ratio, autokorelasi multi-lag)
    yang terbukti paling menentukan pada tugas identifikasi.

    Keduanya digabung setelah attention pooling, bukan di awal: fitur
    struktural bersifat ringkasan satu window dan tidak punya dimensi waktu,
    sehingga menyisipkannya ke tiap timestep hanya akan mengulang nilai sama.
    """
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
    """Arsitektur Hybrid adaptif per timeframe untuk mencapai Generalization Sweet Spot.

    - 1H (data ~6.000 jendela, N_eff ~14 blok):
        BiLSTM 64 unit, Dense 64/32/64, Dropout 0.25, L2 1e-4.
    - 4H (data ~1.400 jendela, N_eff ~3.09 blok):
        BiLSTM 24 unit, Dense 32/16/32, Dropout 0.35, L2 2e-4.
        Penyusutan parameter (~75%) secara efektif mencegah overfitting
        akibat kapasitas berlebih (over-parameterization) pada data 4H.
    """
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
    """Eksperimen ablation order flow (Model A–D).

    Branch SWT IDENTIK di keempat model:
        SWT (L × C) → BiLSTM(64, seq) → Dropout → BiLSTM(32, seq)
        → AttentionPooling → SWT context

    Branch order flow (hanya bila `orderflow_channels` > 0):
        OFI/CVD (L × k) → BiLSTM(16, seq) → GlobalAveragePooling → OF context

    Fusion:
        [SWT context ; OF context] → Dense(16) → Dropout → Softmax(n_classes)

    `orderflow_channels = 0` menghasilkan Model A dengan kepala yang SAMA
    (Dense(16) → Dropout → Softmax), sehingga satu-satunya perbedaan antar
    model adalah ada/tidaknya input order flow.
    """
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
    """Loss gabungan: CE(klasifikasi) + lambda * MSE(regresi H).

    `lambda_regression` menentukan seberapa besar tugas regresi ikut membentuk
    encoder. Nilai bawaan 0.3 dipilih dari skala kedua loss, bukan dari selera:
    cross-entropy tiga kelas bermula di ~1.1, sementara MSE pada H yang
    terkurung di (0, 1) bermula di ~0.01-0.05. Tanpa penimbang, gradien regresi
    praktis tidak terasa; dengan bobot terlalu besar, klasifikasi terabaikan.

    Nilai ini adalah hyperparameter dan memang layak diuji sensitivitasnya —
    tersedia lewat argumen `--lambda-reg` di train_multitask.py.
    """
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=lr),
        loss={"regime": "categorical_crossentropy", "hurst": "mse"},
        loss_weights={"regime": 1.0, "hurst": lambda_regression},
        metrics={"regime": ["accuracy"], "hurst": ["mae"]},
    )
    return model
