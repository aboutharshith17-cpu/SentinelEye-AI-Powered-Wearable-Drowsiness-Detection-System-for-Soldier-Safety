"""
data_prep.py
Data preparation pipeline for DrowsyNet-Small
Downloads and processes datasets (CEW, MRL Eye, NTHU Drowsy)
Includes augmentation and dataset splitting
"""

import os
import sys
import yaml
import json
import random
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import pandas as pd
from sklearn.model_selection import train_test_split
from tqdm import tqdm

class DataAugmentor:
    """Data augmentation for eye region images"""
    def __init__(self, target_size=(28, 28)):
        self.target_size = target_size

    def __call__(self, image, n_augmentations=5):
        """Apply random augmentations"""
        augmented = [self._preprocess(image)]

        for _ in range(n_augmentations):
            img = image.copy()

            # Random rotation (-15 to 15 degrees)
            angle = random.uniform(-15, 15)
            img = img.rotate(angle, expand=False)

            # Random brightness
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(random.uniform(0.7, 1.3))

            # Random contrast
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(random.uniform(0.8, 1.2))

            # Random horizontal flip
            if random.random() > 0.5:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)

            # Random noise
            if random.random() > 0.5:
                img_arr = np.array(img)
                noise = np.random.normal(0, 5, img_arr.shape).astype(np.uint8)
                img_arr = np.clip(img_arr.astype(int) + noise, 0, 255).astype(np.uint8)
                img = Image.fromarray(img_arr)

            # Random blur
            if random.random() > 0.7:
                img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))

            augmented.append(self._preprocess(img))

        return augmented

    def _preprocess(self, image):
        """Standard preprocessing"""
        img = image.resize(self.target_size, Image.LANCZOS)
        img = img.convert('RGB')
        return img

def download_cew_dataset(output_dir):
    """Download Closed Eyes in the Wild dataset"""
    print("Processing CEW dataset...")

    # CEW structure: open_eyes/ and closed_eyes/ folders
    cew_classes = {
        'open': output_dir / 'raw' / 'cew' / 'open_eyes',
        'closed': output_dir / 'raw' / 'cew' / 'closed_eyes'
    }

    augmentor = DataAugmentor(target_size=(24, 24))
    processed_images = []
    processed_labels = []

    class_map = {'open': 0, 'closed': 1}

    for class_name, class_dir in cew_classes.items():
        if not class_dir.exists():
            print(f"Warning: {class_dir} not found")
            continue

        label = class_map[class_name]
        image_files = list(class_dir.glob('*.jpg')) + list(class_dir.glob('*.png'))

        print(f"  {class_name}: {len(image_files)} images")

        for img_path in tqdm(image_files):
            try:
                img = Image.open(img_path).convert('RGB')
                augmented = augmentor(img, n_augmentations=3)

                for aug_img in augmented:
                    processed_images.append(np.array(aug_img))
                    processed_labels.append(label)
            except Exception as e:
                print(f"  Error processing {img_path}: {e}")

    return processed_images, processed_labels

def download_mrl_dataset(output_dir):
    """Download MRL Eye Dataset"""
    print("Processing MRL Eye dataset...")

    mrl_classes = {
        'open': output_dir / 'raw' / 'mrl' / 'Open_Eyes',
        'closed': output_dir / 'raw' / 'mrl' / 'Closed_Eyes'
    }

    augmentor = DataAugmentor(target_size=(24, 24))
    processed_images = []
    processed_labels = []

    class_map = {'open': 0, 'closed': 1}

    for class_name, class_dir in mrl_classes.items():
        if not class_dir.exists():
            print(f"Warning: {class_dir} not found")
            continue

        label = class_map[class_name]
        image_files = list(class_dir.glob('*.png'))

        print(f"  {class_name}: {len(image_files)} images")

        for img_path in tqdm(image_files):
            try:
                img = Image.open(img_path).convert('RGB')
                augmented = augmentor(img, n_augmentations=3)

                for aug_img in augmented:
                    processed_images.append(np.array(aug_img))
                    processed_labels.append(label)
            except Exception as e:
                print(f"  Error processing {img_path}: {e}")

    return processed_images, processed_labels

def create_drowsy_detection_dataset(output_dir, n_samples=10000):
    """Create synthetic drowsy vs awake dataset from face images"""
    print(f"Creating synthetic drowsy detection dataset ({n_samples} samples)...")

    augmentor = DataAugmentor(target_size=(24, 24))

    # Class 0: Awake (open eyes, bright)
    awake_images = []
    for i in tqdm(range(n_samples // 3), desc="Awake"):
        # Generate bright, high-contrast "eye-like" pattern
        img = np.zeros((24, 24, 3), dtype=np.uint8)
        # Bright iris (dark on light)
        cv2.ellipse(img, (12, 12), (8, 5), 0, 0, 360, (150, 150, 150), -1)
        # Dark pupil
        cv2.circle(img, (12, 12), 4, (0, 0, 0), -1)
        # Light reflection
        cv2.circle(img, (10, 10), 1, (255, 255, 255), -1)
        # Bright sclera
        cv2.ellipse(img, (12, 12), (10, 7), 0, 0, 360, (220, 220, 220), 2)

        img_pil = Image.fromarray(img)
        augmented = augmentor(img_pil, n_augmentations=2)
        awake_images.extend([np.array(a) for a in augmented])

    # Class 1: Drowsy (semi-closed)
    drowsy_images = []
    for i in tqdm(range(n_samples // 3), desc="Drowsy"):
        img = np.zeros((24, 24, 3), dtype=np.uint8)
        # Semi-closed eye (narrow opening)
        cv2.ellipse(img, (12, 14), (8, 3), 0, 0, 180, (100, 100, 100), -1)
        cv2.ellipse(img, (12, 12), (8, 5), 0, 180, 360, (120, 120, 120), -1)
        # Dark slit pupil
        cv2.ellipse(img, (12, 13), (6, 1), 0, 0, 180, (20, 20, 20), -1)

        img_pil = Image.fromarray(img)
        augmented = augmentor(img_pil, n_augmentations=2)
        drowsy_images.extend([np.array(a) for a in augmented])

    # Class 2: Asleep (fully closed)
    asleep_images = []
    for i in tqdm(range(n_samples // 3), desc="Asleep"):
        img = np.zeros((24, 24, 3), dtype=np.uint8)
        # Closed eye (horizontal line)
        cv2.ellipse(img, (12, 12), (10, 6), 0, 0, 360, (140, 140, 140), 2)
        cv2.line(img, (2, 12), (22, 12), (120, 120, 120), 3)
        # Eyelashes
        for j in range(3):
            cv2.line(img, (5+j*6, 11), (6+j*6, 9), (40, 40, 40), 1)

        img_pil = Image.fromarray(img)
        augmented = augmentor(img_pil, n_augmentations=2)
        asleep_images.extend([np.array(a) for a in augmented])

    # Balance classes
    min_count = min(len(awake_images), len(drowsy_images), len(asleep_images))
    awake_images = awake_images[:min_count]
    drowsy_images = drowsy_images[:min_count]
    asleep_images = asleep_images[:min_count]

    all_images = awake_images + drowsy_images + asleep_images
    all_labels = [0] * min_count + [1] * min_count + [2] * min_count

    print(f"Total samples: {len(all_images)}")
    print(f"  Awake: {min_count}")
    print(f"  Drowsy: {min_count}")
    print(f"  Asleep: {min_count}")

    return all_images, all_labels

def save_dataset(images, labels, output_dir):
    """Save processed dataset"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as numpy arrays
    images_array = np.array(images, dtype=np.uint8)
    labels_array = np.array(labels, dtype=np.int64)

    np.save(output_dir / 'images.npy', images_array)
    np.save(output_dir / 'labels.npy', labels_array)

    print(f"Dataset saved: {output_dir}")
    print(f"  Images: {images_array.shape}")
    print(f"  Labels: {labels_array.shape}")

    # Save class distribution
    unique, counts = np.unique(labels_array, return_counts=True)
    class_dist = {int(k): int(v) for k, v in zip(unique, counts)}
    print(f"  Class distribution: {class_dist}")

    return images_array, labels_array

def split_dataset(images, labels, train_ratio=0.8, val_ratio=0.15, test_ratio=0.05):
    """Split dataset into train/val/test"""
    print(f"Splitting dataset: {train_ratio:.0%} train / {val_ratio:.0%} val / {test_ratio:.0%} test")

    # First split: train vs (val+test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        images, labels, test_size=(1 - train_ratio), random_state=42, stratify=labels
    )

    # Second split: val vs test
    val_size = val_ratio / (val_ratio + test_ratio)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=(1 - val_size), random_state=42, stratify=y_temp
    )

    print(f"  Train: {len(X_train)} ({len(X_train)*100/len(images):.0f}%)")
    print(f"  Val: {len(X_val)} ({len(X_val)*100/len(images):.0f}%)")
    print(f"  Test: {len(X_test)} ({len(X_test)*100/len(images):.0f}%)")

    return (X_train, y_train), (X_val, y_val), (X_test, y_test)

def main(args):
    """Main data preparation pipeline"""
    print("="*60)
    print("SentinelEye Data Preparation Pipeline")
    print("="*60)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_images = []
    all_labels = []

    # Process CEW dataset
    if args.dataset == 'all' or args.dataset == 'cew':
        imgs, lbls = download_cew_dataset(output_dir)
        all_images.extend(imgs)
        all_labels.extend(lbls)

    # Process MRL dataset
    if args.dataset == 'all' or args.dataset == 'mrl':
        imgs, lbls = download_mrl_dataset(output_dir)
        all_images.extend(imgs)
        all_labels.extend(lbls)

    # Create synthetic drowsy dataset
    if args.dataset == 'all' or args.dataset == 'synthetic':
        imgs, lbls = create_drowsy_detection_dataset(output_dir, args.n_samples)
        all_images.extend(imgs)
        all_labels.extend(lbls)

    if not all_images:
        print("ERROR: No data processed!")
        sys.exit(1)

    # Save full dataset
    images_array, labels_array = save_dataset(all_images, all_labels, output_dir / 'full')

    # Split dataset
    (X_train, y_train), (X_val, y_val), (X_test, y_test) = split_dataset(
        images_array, labels_array
    )

    # Save splits
    save_dataset(list(X_train), list(y_train), output_dir / 'train')
    save_dataset(list(X_val), list(y_val), output_dir / 'val')
    save_dataset(list(X_test), list(y_test), output_dir / 'test')

    # Save metadata
    metadata = {
        'dataset_name': 'SentinelEye-DrowsyNet',
        'num_classes': 3,
        'class_names': ['awake', 'drowsy', 'asleep'],
        'input_size': [24, 24, 3],
        'total_samples': len(all_images),
        'train_samples': len(X_train),
        'val_samples': len(X_val),
        'test_samples': len(X_test),
        'created_at': datetime.now().isoformat(),
        'augmentation': 'Random rotation, flip, brightness, contrast, noise, blur'
    }

    with open(output_dir / 'metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    print("\nData preparation complete!")
    print(f"Output: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='SentinelEye Data Preparation')
    parser.add_argument('--dataset', type=str, default='synthetic',
                        choices=['all', 'cew', 'mrl', 'synthetic'],
                        help='Dataset to process')
    parser.add_argument('--output-dir', type=str, default='data/processed',
                        help='Output directory')
    parser.add_argument('--n-samples', type=int, default=15000,
                        help='Number of synthetic samples')

    args = parser.parse_args()
    main(args)
