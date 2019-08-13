#!/usr/bin/env python
# coding: utf-8

# # Library Imports

# ### File Directory Libraries

# In[ ]:


import os

# ### Math Libraries

# In[ ]:


import numpy as np

# ### Data Pre-Processing Libraries

# In[ ]:


import pandas as pd
import librosa
import soundfile
import cv2
from sklearn.model_selection import KFold
from sklearn.preprocessing import LabelBinarizer

# ### Deep Learning Libraries

# In[ ]:


import tensorflow as tf
import tensorflow.keras as keras
from tensorflow.keras import Input, layers, optimizers, backend as K
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

# # Initialization of Variables

# In[ ]:


GUNSHOT_FREQUENCY_THESHOLD = 0.25
SAMPLE_RATE_PER_SECOND = 22050
SAMPLE_RATE_PER_TWO_SECONDS = 44100
SOUND_FILE_ID = 0
BASE_DIRECTORY = "/home/alexm/Datasets/"
DATA_DIRECTORY = BASE_DIRECTORY + "REU_Samples_and_Labels/"
SOUND_DATA_DIRECTORY = DATA_DIRECTORY + "Samples/"
samples = []
labels = []
sound_file_names = []
sample_weights = []

# # Data Pre-Processing

# ## Reading in the CSV file of descriptors for many kinds of sounds

# In[ ]:


sound_types = pd.read_csv(DATA_DIRECTORY + "labels.csv")


# ## Data augmentation functions

# In[ ]:


def time_shift(wav):
    start_ = int(np.random.uniform(-7000, 7000))
    if start_ >= 0:
        wav_time_shift = np.r_[wav[start_:], np.random.uniform(-0.001, 0.001, start_)]
    else:
        wav_time_shift = np.r_[np.random.uniform(-0.001, 0.001, -start_), wav[:start_]]
    return wav_time_shift


def change_pitch(wav, sample_rate):
    magnitude = (np.random.uniform(-0.1, 0.1))
    wav_pitch_change = librosa.effects.pitch_shift(wav, sample_rate, magnitude)
    return wav_pitch_change


def speed_change(wav):
    speed_rate = np.random.uniform(0.7, 1.3)
    wav_speed_tune = cv2.resize(wav, (1, int(len(wav) * speed_rate))).squeeze()

    if len(wav_speed_tune) < len(wav):
        pad_len = len(wav) - len(wav_speed_tune)
        wav_speed_tune = np.r_[np.random.uniform(-0.0001, 0.0001, int(pad_len / 2)),
                               wav_speed_tune,
                               np.random.uniform(-0.0001, 0.0001, int(np.ceil(pad_len / 2)))]
    else:
        cut_len = len(wav_speed_tune) - len(wav)
        wav_speed_tune = wav_speed_tune[int(cut_len / 2): int(cut_len / 2) + len(wav)]
    return wav_speed_tune


def change_volume(wav, magnitude):
    # 0 < x < 1 quieter; x = 1 identity; x > 1 louder
    wav_volume_change = np.multiply(np.array([magnitude]), wav)
    return wav_volume_change


def add_background(wav, file, data_directory, label_to_avoid):
    label_csv = data_directory + "labels.csv"
    sound_types = pd.read_csv(label_csv)
    sound_directory = data_directory + "Samples/"
    bg_files = os.listdir(sound_directory)
    bg_files.remove(file)
    chosen_bg_file = bg_files[np.random.randint(len(bg_files))]
    jndex = int(chosen_bg_file.split('.')[0])
    while sound_types.loc[sound_types["ID"] == jndex, "Class"].values[0] == label_to_avoid:
        chosen_bg_file = bg_files[np.random.randint(len(bg_files))]
        jndex = int(chosen_bg_file.split('.')[0])
    bg, sr = librosa.load(sound_directory + chosen_bg_file)
    ceil = max((bg.shape[0] - wav.shape[0]), 1)
    start_ = np.random.randint(ceil)
    bg_slice = bg[start_: start_ + wav.shape[0]]
    if bg_slice.shape[0] < wav.shape[0]:
        pad_len = wav.shape[0] - bg_slice.shape[0]
        bg_slice = np.r_[np.random.uniform(-0.001, 0.001, int(pad_len / 2)), bg_slice, np.random.uniform(-0.001, 0.001,
                                                                                                         int(np.ceil(
                                                                                                             pad_len / 2)))]
    wav_with_bg = wav * np.random.uniform(0.8, 1.2) + bg_slice * np.random.uniform(0, 0.5)
    return wav_with_bg


# ## Augmenting data (i.e. time shifting, speed changing, etc.)

# In[ ]:


print("...Parsing Sizheng microphone true positive sound data...")
true_positives_directory = "/home/amorehe/Datasets/true_positives/"
true_positive_samples = []
true_positive_labels = []
true_positive_sound_file_names = []
label = 1

for file in os.listdir(true_positives_directory):
    if file.endswith(".wav"):
        try:
            # Adding 2 second-long samples to the list of samples
            sample, sample_rate = librosa.load(true_positives_directory + file)

            if len(sample) <= sample_rate_per_two_seconds:
                number_of_missing_hertz = sample_rate_per_two_seconds - len(sample)
                padded_sample = np.array(sample.tolist() + [0 for i in range(number_of_missing_hertz)])

                true_positive_samples.append(padded_sample)
                true_positive_labels.append(label)
                true_positive_sound_file_names.append(file)
            else:
                for i in range(0, sample.size - sample_rate_per_two_seconds, sample_rate_per_two_seconds):
                    sample_slice = sample[i: i + sample_rate_per_two_seconds]
                    true_positive_samples.append(sample_slice)
                    true_positive_labels.append(label)
                    true_positive_sound_file_names.append(file)

            print("Finished parsing a true positive sample:", file)

        except:
            sample, sample_rate = soundfile.read(true_positives_directory + file)
            print("Sound(s) not recognized by Librosa:", file)
            pass

true_positive_samples = np.array(true_positive_samples)
true_positive_labels = np.array(true_positive_labels)
number_of_augmentations = 5
augmented_samples = np.zeros(
    (true_positive_samples.shape[0] * (number_of_augmentations + 1), true_positive_samples.shape[1]))
augmented_labels = np.zeros((true_positive_labels.shape[0] * (number_of_augmentations + 1),))
j = 0

for i in range(0, len(augmented_samples), (number_of_augmentations + 1)):
    file = true_positive_sound_file_names[j]

    augmented_samples[i, :] = true_positive_samples[j, :]
    augmented_samples[i + 1, :] = time_shift(true_positive_samples[j, :])
    augmented_samples[i + 2, :] = change_pitch(true_positive_samples[j, :], sample_rate)
    augmented_samples[i + 3, :] = speed_change(true_positive_samples[j, :])
    augmented_samples[i + 4, :] = change_volume(true_positive_samples[j, :], np.random.uniform())

    bg_files = os.listdir(true_positives_directory)
    bg_files.remove(file)
    chosen_bg_file = bg_files[np.random.randint(len(bg_files))]
    bg, sr = librosa.load(true_positives_directory + chosen_bg_file)
    ceil = max((bg.shape[0] - true_positive_samples[j, :].shape[0]), 1)
    start_ = np.random.randint(ceil)
    bg_slice = bg[start_: start_ + true_positive_samples[j, :].shape[0]]
    if bg_slice.shape[0] < true_positive_samples[j, :].shape[0]:
        pad_len = true_positive_samples[j, :].shape[0] - bg_slice.shape[0]
        bg_slice = np.r_[
            np.random.uniform(-0.001, 0.001, int(pad_len / 2)), bg_slice, np.random.uniform(-0.001, 0.001, int(
                np.ceil(pad_len / 2)))]
    wav_with_bg = true_positive_samples[j, :] * np.random.uniform(0.8, 1.2) + bg_slice * np.random.uniform(0, 0.5)

    augmented_samples[i + 5, :] = wav_with_bg

    augmented_labels[i] = true_positive_labels[j]
    augmented_labels[i + 1] = true_positive_labels[j]
    augmented_labels[i + 2] = true_positive_labels[j]
    augmented_labels[i + 3] = true_positive_labels[j]
    augmented_labels[i + 4] = true_positive_labels[j]
    augmented_labels[i + 5] = true_positive_labels[j]
    j += 1

    print("Finished augmenting a true positive sample:", file)

true_positive_samples = augmented_samples
true_positive_labels = augmented_labels

print(
    "The number of true positive samples available for training is currently " + str(len(true_positive_samples)) + '.')
print("The number of true positive labels available for training is currently " + str(len(true_positive_labels)) + '.')

print("...Parsing Sizheng microphone false positive sound data...")
false_positives_directory = "/home/amorehe/Datasets/false_positives/"
false_positive_samples = []
false_positive_labels = []
false_positive_sound_file_names = []
label = 0

for file in os.listdir(false_positives_directory):
    if file.endswith(".wav"):
        try:
            # Adding 2 second-long samples to the list of samples
            sample, sample_rate = librosa.load(false_positives_directory + file)

            if len(sample) <= sample_rate_per_two_seconds:
                number_of_missing_hertz = sample_rate_per_two_seconds - len(sample)
                padded_sample = np.array(sample.tolist() + [0 for i in range(number_of_missing_hertz)])

                false_positive_samples.append(padded_sample)
                false_positive_labels.append(label)
                false_positive_sound_file_names.append(file)
            else:
                for i in range(0, sample.size - sample_rate_per_two_seconds, sample_rate_per_two_seconds):
                    sample_slice = sample[i: i + sample_rate_per_two_seconds]
                    false_positive_samples.append(sample_slice)
                    false_positive_labels.append(label)
                    false_positive_sound_file_names.append(file)

            print("Finished parsing a false positive sample:", file)


        except:
            sample, sample_rate = soundfile.read(false_positives_directory + file)
            print("Sound(s) not recognized by Librosa:", file)
            pass

false_positive_samples = np.array(false_positive_samples)
false_positive_labels = np.array(false_positive_labels)
number_of_augmentations = 5
augmented_samples = np.zeros(
    (false_positive_samples.shape[0] * (number_of_augmentations + 1), false_positive_samples.shape[1]))
augmented_labels = np.zeros((false_positive_labels.shape[0] * (number_of_augmentations + 1),))
j = 0

for i in range(0, len(augmented_samples), (number_of_augmentations + 1)):
    file = false_positive_sound_file_names[j]

    augmented_samples[i, :] = false_positive_samples[j, :]
    augmented_samples[i + 1, :] = time_shift(false_positive_samples[j, :])
    augmented_samples[i + 2, :] = change_pitch(false_positive_samples[j, :], sample_rate)
    augmented_samples[i + 3, :] = speed_change(false_positive_samples[j, :])
    augmented_samples[i + 4, :] = change_volume(false_positive_samples[j, :], np.random.uniform())

    bg_files = os.listdir(false_positives_directory)
    bg_files.remove(file)
    chosen_bg_file = bg_files[np.random.randint(len(bg_files))]
    bg, sr = librosa.load(false_positives_directory + chosen_bg_file)
    ceil = max((bg.shape[0] - false_positive_samples[j, :].shape[0]), 1)
    start_ = np.random.randint(ceil)
    bg_slice = bg[start_: start_ + false_positive_samples[j, :].shape[0]]
    if bg_slice.shape[0] < false_positive_samples[j, :].shape[0]:
        pad_len = false_positive_samples[j, :].shape[0] - bg_slice.shape[0]
        bg_slice = np.r_[
            np.random.uniform(-0.001, 0.001, int(pad_len / 2)), bg_slice, np.random.uniform(-0.001, 0.001, int(
                np.ceil(pad_len / 2)))]
    wav_with_bg = false_positive_samples[j, :] * np.random.uniform(0.8, 1.2) + bg_slice * np.random.uniform(0, 0.5)

    augmented_samples[i + 5, :] = wav_with_bg

    augmented_labels[i] = false_positive_labels[j]
    augmented_labels[i + 1] = false_positive_labels[j]
    augmented_labels[i + 2] = false_positive_labels[j]
    augmented_labels[i + 3] = false_positive_labels[j]
    augmented_labels[i + 4] = false_positive_labels[j]
    augmented_labels[i + 5] = false_positive_labels[j]
    j += 1

    print("Finished augmenting a false positive sample:", file)

false_positive_samples = augmented_samples
false_positive_labels = augmented_labels

print("The number of false positive samples available for training is currently " + str(
    len(false_positive_samples)) + '.')
print(
    "The number of false positive labels available for training is currently " + str(len(false_positive_labels)) + '.')

# ## Loading augmented sample file and label file as numpy arrays

# In[ ]:


samples = np.load(BASE_DIRECTORY + "gunshot_augmented_sound_samples.npy")
labels = np.load(BASE_DIRECTORY + "gunshot_augmented_sound_labels.npy")

samples = np.concatenate([samples, true_positive_samples])
labels = np.concatenate([labels, true_positive_labels])
samples = np.concatenate([samples, false_positive_samples])
labels = np.concatenate([labels, false_positive_labels])

np.save(BASE_DIRECTORY + "gunshot_augmented_sound_samples.npy", samples)
np.save(BASE_DIRECTORY + "gunshot_augmented_sound_labels.npy", labels)

print("Finished concatenating the new true/false positive samples...")