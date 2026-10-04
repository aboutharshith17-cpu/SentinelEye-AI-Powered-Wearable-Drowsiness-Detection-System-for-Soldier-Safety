"""
train_drowsynet.py
Training pipeline for DrowsyNet-Small
Includes data augmentation, mixed precision, and quantization-aware training
"""

import os
import sys
import yaml
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from torch.cuda.amp import GradScaler, autocast
from torch.profiler import profile, record_function, ProfilerActivity
import torchvision
from torchvision import datasets, transforms

from drowsynet_small import DrowsyNetSmall
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
import numpy as np

class EarlyStopping:
    """Early stopping to prevent overfitting"""
    def __init__(self, patience=10, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float('inf')
        self.early_stop = False

    def __call__(self, val_loss):
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        return self.early_stop

class MetricsTracker:
    """Track and log training metrics"""
    def __init__(self):
        self.train_losses = []
        self.val_losses = []
        self.train_accuracies = []
        self.val_accuracies = []
        self.learning_rates = []
        self.best_val_acc = 0.0
        self.best_epoch = 0

    def update(self, train_loss, val_loss, train_acc, val_acc, lr):
        self.train_losses.append(train_loss)
        self.val_losses.append(val_loss)
        self.train_accuracies.append(train_acc)
        self.val_accuracies.append(val_acc)
        self.learning_rates.append(lr)

        if val_acc > self.best_val_acc:
            self.best_val_acc = val_acc
            self.best_epoch = len(self.val_accuracies) - 1

    def to_dict(self):
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'train_accuracies': self.train_accuracies,
            'val_accuracies': self.val_accuracies,
            'learning_rates': self.learning_rates,
            'best_val_accuracy': self.best_val_acc,
            'best_epoch': self.best_epoch
        }

def get_data_transforms():
    """Define data augmentation pipelines"""
    train_transform = transforms.Compose([
        transforms.Resize((32, 32)),
        transforms.RandomCrop(28),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.2, scale=(0.02, 0.1))
    ])

    val_transform = transforms.Compose([
        transforms.Resize((32, 32)),
        transforms.CenterCrop(28),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                            std=[0.229, 0.224, 0.225])
    ])

    return train_transform, val_transform

def create_dummy_dataloader(batch_size=32, num_samples=1000):
    """Create dummy datasets for testing (replace with real data)"""
    # Create synthetic data: 3 classes
    data = torch.randn(num_samples, 3, 28, 28)
    targets = torch.randint(0, 3, (num_samples,))

    dataset = torch.utils.data.TensorDataset(data, targets)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

    return train_dataset, val_dataset

def train_epoch(model, dataloader, criterion, optimizer, scaler, device, epoch, total_epochs):
    """Train for one epoch"""
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (data, target) in enumerate(dataloader):
        data, target = data.to(device), target.to(device)

        optimizer.zero_grad()

        with autocast(enabled=(device.type == 'cuda')):
            output = model(data)
            loss = criterion(output, target)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item()
        _, predicted = output.max(1)
        total += target.size(0)
        correct += predicted.eq(target).sum().item()

        if batch_idx % 50 == 0:
            print(f"Epoch [{epoch}/{total_epochs}] "
                  f"Batch [{batch_idx}/{len(dataloader)}] "
                  f"Loss: {loss.item():.4f} "
                  f"Acc: {100.*correct/total:.2f}%")

    epoch_loss = running_loss / len(dataloader)
    epoch_acc = 100. * correct / total
    return epoch_loss, epoch_acc

def validate_epoch(model, dataloader, criterion, device):
    """Validate for one epoch"""
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for data, target in dataloader:
            data, target = data.to(device), target.to(device)
            output = model(data)
            loss = criterion(output, target)

            running_loss += loss.item()
            _, predicted = output.max(1)
            total += target.size(0)
            correct += predicted.eq(target).sum().item()

            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(target.cpu().numpy())

    epoch_loss = running_loss / len(dataloader)
    epoch_acc = 100. * correct / total

    # Compute precision, recall, F1
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_targets, all_preds, average='weighted', zero_division=0
    )

    # Confusion matrix
    cm = confusion_matrix(all_targets, all_preds)

    print(f"\nValidation - Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.2f}%")
    print(f"Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1:.4f}")
    print("Confusion Matrix:")
    print(cm)

    return epoch_loss, epoch_acc, precision, recall, f1

def quantize_model(model, example_input):
    """Post-training INT8 quantization for edge deployment"""
    print("Quantizing model to INT8...")

    model.eval()
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {nn.Linear, nn.Conv2d},
        dtype=torch.qint8
    )

    # Calibrate with sample data
    with torch.no_grad():
        _ = quantized_model(example_input)

    return quantized_model

def save_model(model, save_path, metrics=None):
    """Save model and metrics"""
    torch.save({
        'model_state_dict': model.state_dict(),
        'model_class': 'DrowsyNetSmall',
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics
    }, save_path)
    print(f"Model saved to {save_path}")

def export_to_tflite(model, example_input, save_path):
    """Export to TFLite format for embedded deployment"""
    try:
        from torch2trt import torch2trt
        import tensorflow as tf
        from torchvision.models.quantization import quantize_dynamic
    except ImportError:
        print("Warning: torch2trt/tf not available, skipping TFLite export")
        return None

    model.eval()
    with torch.no_grad():
        trt_model = torch2trt(model, [example_input])

    # Convert to ONNX first
    onnx_path = save_path.replace('.tflite', '.onnx')
    torch.onnx.export(trt_model, example_input, onnx_path,
                      export_params=True, opset_version=13,
                      do_constant_folding=True,
                      input_names=['input'], output_names=['output'])

    print(f"ONNX export: {onnx_path}")

    # Convert ONNX to TFLite using tf
    try:
        import onnx
        from onnx_tf.backend import prepare
        onnx_model = onnx.load(onnx_path)
        tf_rep = prepare(onnx_model)

        # Convert to TFLite
        converter = tf.lite.TFLiteConverter.from_keras_model(tf_rep.keras_graph)
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.target_spec.supported_types = [tf.int8]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8

        tflite_model = converter.convert()

        with open(save_path, 'wb') as f:
            f.write(tflite_model)

        print(f"TFLite model saved: {save_path} ({len(tflite_model)} bytes)")
        return save_path

    except Exception as e:
        print(f"TFLite conversion failed: {e}")
        return None

def main(args):
    """Main training loop"""
    print("="*60)
    print("SentinelEye DrowsyNet-Small Training Pipeline")
    print("="*60)

    # Device setup
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")
    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Create model
    model = DrowsyNetSmall(num_classes=3)
    model = model.to(device)
    print(f"\nModel: {model.get_param_count():,} parameters, "
          f"{model.get_model_size_mb():.2f} MB (FP32)")

    # Loss and optimizer
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=args.epochs // 4, T_mult=2
    )
    scaler = GradScaler(enabled=(device.type == 'cuda'))

    # Data loading
    print("\nLoading data...")
    train_transform, val_transform = get_data_transforms()

    if args.data_dir and os.path.exists(args.data_dir):
        # Use real data
        train_dataset = datasets.ImageFolder(os.path.join(args.data_dir, 'train'),
                                              transform=train_transform)
        val_dataset = datasets.ImageFolder(os.path.join(args.data_dir, 'val'),
                                           transform=val_transform)
    else:
        # Use dummy data
        print("WARNING: No data directory found, using synthetic data!")
        train_dataset, val_dataset = create_dummy_dataloader(batch_size=args.batch_size)

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size,
                              shuffle=True, num_workers=0, pin_memory=False)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size,
                           shuffle=False, num_workers=0, pin_memory=False)

    print(f"Training samples: {len(train_dataset)}")
    print(f"Validation samples: {len(val_dataset)}")

    # Metrics tracker
    metrics = MetricsTracker()
    early_stopping = EarlyStopping(patience=args.patience)
    best_val_acc = 0.0

    # Training loop
    start_time = time.time()
    print(f"\nStarting training for {args.epochs} epochs...")

    for epoch in range(1, args.epochs + 1):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch}/{args.epochs}")

        train_loss, train_acc = train_epoch(model, train_loader, criterion,
                                            optimizer, scaler, device, epoch, args.epochs)
        val_loss, val_acc, precision, recall, f1 = validate_epoch(model, val_loader, criterion, device)

        scheduler.step()
        current_lr = optimizer.param_groups[0]['lr']

        metrics.update(train_loss, val_loss, train_acc, val_acc, current_lr)

        print(f"\nEpoch {epoch} Summary:")
        print(f"  Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        print(f"  Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
        print(f"  F1 Score: {f1:.4f}, LR: {current_lr:.6f}")
        print(f"  Best Val Acc: {max(metrics.val_accuracies):.2f}% at epoch {metrics.best_epoch + 1}")

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            save_model(model, os.path.join(args.save_dir, 'best_model.pth'), metrics.to_dict())
            print(f"  *** New best model saved! ***")

        # Early stopping
        if early_stopping(val_loss):
            print(f"\nEarly stopping triggered at epoch {epoch}")
            break

    total_time = time.time() - start_time
    print(f"\nTraining completed in {total_time / 3600:.2f} hours")
    print(f"Best Validation Accuracy: {best_val_acc:.2f}%")

    # Final quantization and export
    print("\nQuantizing and exporting model...")
    example_input = torch.randn(1, 3, 24, 24).to(device)

    with torch.no_grad():
        quantized_model = quantize_model(model, example_input)

    # Save quantized model
    quantized_path = os.path.join(args.save_dir, 'drowsynet_quantized.pth')
    torch.jit.save(torch.jit.script(quantized_model), quantized_path)
    print(f"Quantized model saved: {quantized_path}")

    # Export to TFLite
    tflite_path = os.path.join(args.save_dir, 'drowsynet.tflite')
    export_to_tflite(model, example_input, tflite_path)

    # Save final metrics
    with open(os.path.join(args.save_dir, 'training_metrics.json'), 'w') as f:
        json.dump(metrics.to_dict(), f, indent=2)

    # Print final summary
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Best Validation Accuracy: {best_val_acc:.2f}%")
    print(f"Model Size (FP32): {model.get_model_size_mb():.2f} MB")
    print(f"Model Size (INT8): {model.get_model_size_mb() / 4:.2f} MB")
    print(f"Parameters: {model.get_param_count():,}")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='DrowsyNet-Small Training')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Path to dataset directory')
    parser.add_argument('--save-dir', type=str, default='checkpoints',
                        help='Directory to save models')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Training batch size')
    parser.add_argument('--lr', type=float, default=1e-3,
                        help='Learning rate')
    parser.add_argument('--patience', type=int, default=10,
                        help='Early stopping patience')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed')

    args = parser.parse_args()

    # Set random seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    # Create save directory
    os.makedirs(args.save_dir, exist_ok=True)

    # Run training
    main(args)
