import math
import os

import numpy as np
from PIL import ImageEnhance
from keras.preprocessing import image as ki
from keras.preprocessing.image import ImageDataGenerator
from keras.utils.data_utils import Sequence
from six.moves import range


class MultipleOutputsDirectorySequence(Sequence):
    """Iterator capable of creating (images, {painters, styles, ...}) pairs
       from a directory.
    """

    def __init__(self, directory,
                 outputs: dict,
                 name_map: dict,
                 image_data_generator: ImageDataGenerator,
                 batch_size: int = 32,
                 target_size=None,
                 subdirectories=None,
                 shuffle: bool = True):
        self.directory = directory
        self.outputs = outputs
        self.name_map = name_map
        self.image_data_generator = image_data_generator
        self.batch_size = batch_size
        self.target_size = target_size
        self.shuffle = shuffle

        samples = []
        if not directory.endswith('/'):
            directory += '/'
        self.subdirectories = np.asarray(subdirectories or sorted(os.listdir(directory)))
        for c in self.subdirectories:
            samples += [directory + c + '/' + f for f in os.listdir(directory + c)]

        if self.shuffle:
            np.random.shuffle(samples)

        files_base = [os.path.basename(f).split('-')[0] for f in samples]
        self.samples = np.asarray(samples)
        self.classes = np.array([name_map[f] for f in files_base])

    def __len__(self):
        return math.ceil(len(self.samples) / self.batch_size)

    def __getitem__(self, idx):
        f_batch = self.samples[idx * self.batch_size:(idx + 1) * self.batch_size]
        y_batch = self.classes[idx * self.batch_size:(idx + 1) * self.batch_size]

        x_batch = []
        for filename in f_batch:
            x = ki.img_to_array(ki.load_img(filename, target_size=self.target_size))
            x = self.image_data_generator.random_transform(x)
            x = self.image_data_generator.standardize(x)
            x_batch += [x]

        y_batch = {o: y[y_batch] for o, y in self.outputs.items()}
        return np.asarray(x_batch), y_batch


class BalancedDirectoryPairsSequence(Sequence):
    """Iterator capable of creating pairs of images.

    :param batch_size: size of the batch yielded each next(self) call.
    """

    def __init__(self, directory, image_data_generator, batch_size=32,
                 pairs=50, target_size=None, classes=None, shuffle=True):
        self.directory = directory
        self.image_data_generator = image_data_generator
        self.batch_size = batch_size
        self.target_size = target_size
        self.classes = np.asarray(classes or sorted(os.listdir(directory)))
        self.shuffle = shuffle

        if not directory.endswith('/'):
            directory += '/'

        _id = 0
        samples = {}
        for c in self.classes:
            files = os.listdir(directory + c)
            if files:
                samples[_id] = list(map(lambda _f: directory + c + '/' + _f, files))
                _id += 1

        x, y = [], []

        for c1 in range(len(self.classes)):
            x += np.random.choice(samples[c1], pairs).reshape(int(pairs / 2), 2).tolist()
            y += int(pairs / 2) * [1.0]

            others = (np.random.randint(1, len(self.classes), size=int(pairs / 2)) + c1) % len(self.classes)
            x += zip(np.random.choice(samples[c1], int(pairs / 2)), (np.random.choice(samples[c2]) for c2 in others))
            y += int(pairs / 2) * [0.0]

        p = np.arange(len(x))
        if self.shuffle:
            np.random.shuffle(p)
        self.x, self.y = [np.asarray(e)[p] for e in (x, y)]

    def __len__(self):
        return math.ceil(len(self.x) / self.batch_size)

    def __getitem__(self, idx):
        batch_files = self.x[idx * self.batch_size:(idx + 1) * self.batch_size]
        batch_y = self.y[idx * self.batch_size:(idx + 1) * self.batch_size]

        batch_x = [[], []]
        # build batch of image data
        for a, b in batch_files:
            for i, n in enumerate((a, b)):
                x = ki.img_to_array(ki.load_img(n, target_size=self.target_size))
                x = self.image_data_generator.random_transform(x)
                x = self.image_data_generator.standardize(x)
                batch_x[i] += [x]

        batch_x = [np.asarray(_x) for _x in batch_x]
        return batch_x, np.array(batch_y)


class BalancedDirectoryPairsMultipleOutputsSequence(Sequence):
    """Iterator capable of creating pairs of images.

    :param batch_size: size of the batch yielded each next(self) call.
    """

    def __init__(self, directory,
                 outputs: dict,
                 name_map: dict,
                 image_data_generator: ImageDataGenerator,
                 batch_size: int = 32,
                 target_size=None,
                 subdirectories=None,
                 shuffle: bool = True,
                 pairs=50):
        self.directory = directory
        self.outputs = outputs
        self.name_map = name_map
        self.image_data_generator = image_data_generator
        self.batch_size = batch_size
        self.target_size = target_size
        self.shuffle = shuffle

        if not directory.endswith('/'):
            directory += '/'
        self.subdirectories = np.asarray(subdirectories or sorted(os.listdir(directory)))

        _id = 0
        samples = {}
        for c in self.subdirectories:
            files = os.listdir(directory + c)
            if files:
                samples[_id] = list(map(lambda _f: directory + c + '/' + _f, files))
                _id += 1

        x = []
        for c1 in range(len(self.subdirectories)):
            x += np.random.choice(samples[c1], pairs).reshape(int(pairs / 2), 2).tolist()
            others = (np.random.randint(1, len(self.subdirectories), size=int(pairs / 2))
                      + c1) % len(self.subdirectories)
            x += zip(np.random.choice(samples[c1], int(pairs / 2)), (np.random.choice(samples[c2]) for c2 in others))
        p = np.arange(len(x))

        if self.shuffle:
            np.random.shuffle(p)
        self.x = np.asarray(x)[p]

        y = {o: [] for o in outputs}
        indices = [[self.name_map[os.path.basename(f).split('-')[0]] for f in p]
                   for p in self.x]
        for o in outputs:
            _y = outputs[o][indices]
            if o == 'date':
                _y = np.abs(_y[:, 0, :] - _y[:, 1, :])
            else:
                _y = (_y[:, 0, :] == _y[:, 1, :]).astype('float')
            y[o] += _y
        self.y = y

    def __len__(self):
        return math.ceil(len(self.x) / self.batch_size)

    def __getitem__(self, idx):
        batch_files = self.x[idx * self.batch_size:(idx + 1) * self.batch_size]
        batch_y = self.y[idx * self.batch_size:(idx + 1) * self.batch_size]

        batch_x = [[], []]
        # build batch of image data
        for a, b in batch_files:
            for i, n in enumerate((a, b)):
                x = ki.img_to_array(ki.load_img(n, target_size=self.target_size))
                x = self.image_data_generator.random_transform(x)
                x = self.image_data_generator.standardize(x)
                batch_x[i] += [x]

        batch_x = [np.asarray(_x) for _x in batch_x]
        return batch_x, np.array(batch_y)


class PaintingEnhancer:
    def __init__(self, augmentations=('color', 'brightness', 'contrast'),
                 variability=0.25):
        self.augmentations = augmentations
        self.variability = variability

    def process(self, patch):
        if 'color' in self.augmentations:
            enhance = ImageEnhance.Color(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)

        if 'brightness' in self.augmentations:
            enhance = ImageEnhance.Brightness(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)

        if 'contrast' in self.augmentations:
            enhance = ImageEnhance.Contrast(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)
        return patch
