#!/usr/bin/env python
# coding: utf-8

# # Library Imports

# ### File Directory Libraries

# In[ ]:


import glob
import os
from os.path import isdir, join
from pathlib import Path


# ### Math Libraries

# In[ ]:


import numpy as np
from scipy.fftpack import fft
from scipy import signal
import matplotlib.pyplot as plt
import plotly.offline as py
import plotly.graph_objs as go
import plotly.tools as tls


# ### Data Pre-Processing Libraries

# In[ ]:


import pandas as pd
import librosa
import re
from sklearn.model_selection import KFold


# ### Visualization Libraries

# In[ ]:


import seaborn as sns
import IPython.display as ipd
import librosa.display


# ### Deep Learning Libraries

# In[ ]:


import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras import Input, layers, optimizers
from tensorflow.keras import backend as K
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import Dense, Dropout, Flatten
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint


# # Initialization of Variables

# In[ ]:


samples=[]
labels = []
gunshot_frequency_threshold = 0.25
sampling_rate_per_two_seconds = 44100
input_shape = (sampling_rate_per_two_seconds, 1)


# # Data Pre-Processing

# ## Loading augmented sample file and label file as numpy arrays

# In[ ]:


samples = np.load("/home/amorehe/Datasets/gunshot_augmented_sound_samples.npy")
labels = np.load("/home/amorehe/Datasets/gunshot_augmented_sound_labels.npy")

# ## Restructuring the label data


# In[ ]:


labels = keras.utils.to_categorical(labels, 2)


# ### Optional debugging of the label data's shape


# In[ ]:


print(labels.shape)
(21789, 2)


# ## Arranging the data

# In[ ]:


kf = KFold(n_splits=3, shuffle=True)
samples = np.array(samples)
labels = np.array(labels)
for train_index, test_index in kf.split(samples):
    train_wav, test_wav = samples[train_index], samples[test_index]
    train_label, test_label = labels[train_index], labels[test_index]


# ## Reshaping/restructuring the data

# In[ ]:


train_wav = train_wav.reshape(-1, sampling_rate_per_two_seconds, 1)
test_wav = test_wav.reshape(-1, sampling_rate_per_two_seconds, 1)


# ### Optional debugging of the training data's shape

# In[ ]:


print(train_wav.shape)


# # Model


# ## Model Parameters

# In[ ]:


drop_out_rate = 0.1
learning_rate = 0.001
number_of_epochs = 100
batch_size = 32


# ## ROC AUC metric - Uses the import "from keras import backend as K"

# In[ ]:


def auc(y_true, y_pred):
    auc = tf.metrics.auc(y_true, y_pred)[1]
    K.get_session().run(tf.local_variables_initializer())
    return auc


# ## Model Architecture

# In[ ]:


input_tensor = Input(shape=input_shape)
number_of_classes = 2

x = layers.Conv1D(16, 9, activation="relu", padding="same")(input_tensor)
x = layers.Conv1D(16, 9, activation="relu", padding="same")(x)
x = layers.MaxPool1D(16)(x)
x = layers.Dropout(rate=drop_out_rate)(x)

x = layers.Conv1D(32, 3, activation="relu", padding="same")(x)
x = layers.Conv1D(32, 3, activation="relu", padding="same")(x)
x = layers.MaxPool1D(4)(x)
x = layers.Dropout(rate=drop_out_rate)(x)

x = layers.Conv1D(32, 3, activation="relu", padding="same")(x)
x = layers.Conv1D(32, 3, activation="relu", padding="same")(x)
x = layers.MaxPool1D(4)(x)
x = layers.Dropout(rate=drop_out_rate)(x)

x = layers.Conv1D(256, 3, activation="relu", padding="same")(x)
x = layers.Conv1D(256, 3, activation="relu", padding="same")(x)
x = layers.GlobalMaxPool1D()(x)
x = layers.Dropout(rate=drop_out_rate)(x)

x = layers.Dense(64, activation="relu")(x)
x = layers.Dense(1028, activation="relu")(x)
output_tensor = layers.Dense(number_of_classes, activation="softmax")(x)

model = tf.keras.Model(input_tensor, output_tensor)

optimizer = optimizers.Adam(learning_rate, learning_rate / 100)

model.compile(optimizer=optimizer, loss=keras.losses.binary_crossentropy, metrics=["accuracy", auc])


# ## Configuring model properties

# In[ ]:


model_filename = '/home/amorehe/Datasets/gunshot_sound_model.pkl'

model_callbacks = [
    EarlyStopping(monitor='val_acc',
                  patience=10,
                  verbose=1,
                  mode='auto'),
    
    ModelCheckpoint(model_filename, monitor='val_acc',
                    verbose=1,
                    save_best_only=True,
                    mode='auto'),
]


# ### Optional debugging of the model's architecture

# In[ ]:


model.summary()


# ## Training & caching the model

# In[ ]:


model.fit(train_wav, train_label, 
          validation_data=[test_wav, test_label],
          epochs=number_of_epochs,
          callbacks=model_callbacks,
          verbose=1,
          batch_size=batch_size,
          shuffle=True)

model.save("/home/amorehe/Datasets/gunshot_sound_model.h5")


# ### Optional debugging of incorrectly-labeled examples

# In[ ]:


y_test_pred = model.predict(test_wav)
y_predicted_classes_test = y_test_pred.argmax(axis=-1)
y_actual_classes_test= test_label.argmax(axis=-1)
wrong_examples = np.nonzero(y_predicted_classes_test != y_actual_classes_test)
print(wrong_examples)