import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import numpy as np
import os
os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"]="0,1" #gpu 사용
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
from tensorflow import keras
import tensorflow as tf
from tensorflow.keras import layers
from tensorflow.keras.callbacks import EarlyStopping,ReduceLROnPlateau, ModelCheckpoint


df = pd.read_csv('./dataset/EmoDB_mels.csv')
df.drop(['Unnamed: 0','path'], axis=1, inplace=True)
df['emotion'] = df['emotion'].map({
    'neutral' : 0,
    'happiness' : 1,
    'anger' : 2,
    'sadness': 3,
    'fear': 4,
    'disgust' : 5,
    'boredom':6
    })

df = df.fillna(0)
input_data = df.drop(['emotion'], axis=1) #mel_spectogram
target_data= df['emotion'].to_numpy() #감정


time_steps = input_data.shape[1] // 40
remainder = input_data.shape[1] % 40
input_arr = input_data.values

# 40으로 나누어 떨어지지 않을 경우 패딩 추가
if remainder != 0:
    padding_size = 40 - remainder
    padding = np.zeros((input_data.shape[0], padding_size))
    input_arr = np.hstack((input_arr, padding))
    time_steps += 1

input_3d = np.reshape(input_arr,(input_arr.shape[0], time_steps, 40))

train_input, test_input, train_target, test_target=train_test_split(input_3d, target_data, train_size=0.7, random_state=42)
test_input, val_input, test_target, val_target = train_test_split(test_input,test_target,test_size=0.5,random_state=42)

ss=StandardScaler()
train_input = ss.fit_transform(train_input.reshape(-1, train_input.shape[-1])).reshape(train_input.shape)
test_input = ss.fit_transform(test_input.reshape(-1, test_input.shape[-1])).reshape(test_input.shape)
val_input = ss.transform(val_input.reshape(-1, val_input.shape[-1])).reshape(val_input.shape)

class TransformerBlock(layers.Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, rate=0.1):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.ff_dim = ff_dim
        self.rate = rate
        self.att = layers.MultiHeadAttention(num_heads=num_heads, key_dim=embed_dim)
        self.ffn = keras.Sequential(
            [layers.Dense(ff_dim, activation="relu"), layers.Dense(embed_dim),]
        )
        self.layernorm1 = layers.LayerNormalization(epsilon=1e-6)
        self.layernorm2 = layers.LayerNormalization(epsilon=1e-6)
        self.dropout1 = layers.Dropout(rate)
        self.dropout2 = layers.Dropout(rate)

    def call(self, inputs, training):
        attn_output = self.att(inputs, inputs)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        return self.layernorm2(out1 + ffn_output)

    def get_config(self):
        config = super().get_config()
        config.update({
            "embed_dim": self.embed_dim,
            "num_heads": self.num_heads,
            "ff_dim": self.ff_dim,
            "rate": self.rate,
        })
        return config
    
 
num_classes = 7
"""
#콜백함수
reduceLR = ReduceLROnPlateau(monitor='val_loss', factor=0.5, mode='min')
early_stop = EarlyStopping(monitor='val_loss', patience=30)
callbacks_list = [reduceLR, early_stop]
"""
model = keras.Sequential()
model.add(tf.keras.layers.Conv1D(filters=64, kernel_size=3, padding='same', activation='relu', input_shape=(None,40)))
model.add(tf.keras.layers.MaxPooling1D(pool_size=2))
model.add(tf.keras.layers.Bidirectional(tf.keras.layers.GRU(64, return_sequences=True)))
transformer_block = TransformerBlock(128, 4, 64)
model.add(transformer_block)
model.add(tf.keras.layers.GlobalAveragePooling1D())
model.add(tf.keras.layers.Dropout(0.1))
model.add(tf.keras.layers.Dense(num_classes, activation='softmax'))
model.compile("adam", "sparse_categorical_crossentropy", metrics=["accuracy"])
history = model.fit(train_input, train_target, epochs=400, batch_size=32,validation_data=(val_input, val_target))
model.save('./EmoDB_model')
