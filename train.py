from tqdm import tqdm
import os
from PIL import Image
from loss_function import focal_loss_sparse
import numpy as np
import tensorflow as tf
from keras import layers, models
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, confusion_matrix, ConfusionMatrixDisplay
from data_loader import load_train_data
from data_loader import NUM_CLASSES, DEFAULT_SIZE
from tensorflow.python.client import device_lib
from sklearn.metrics import classification_report
import pandas as pd
os.environ["CUDA_VISIBLE_DEVICES"] = "0" #주석 풀어서 gpu 사용

INPUT_SIZE = DEFAULT_SIZE    #TODO 모델에 따라 INPUT_SIZE 조정
EPOCHS = 10
BATCH_SIZE = 64

# 하이퍼파라미터 그리드
#TODO 추가적으로 hyperparameter 조정, ex) dropout, neuron 수...
learning_rates = [1e-4, 1e-3, 1e-2]  
optimizers = ['adam', 'sgd_momentum']
activation_functions = ['relu', 'elu'] #TODO activation function에 따라 kernel_initializer 조정 필요
# TODO activation function에 따라 kernel_initializer 조정 필요
# ex) relu -> kernel_initializer='he_normal'

# Data Load
train_dataset, validation_dataset = load_train_data(img_size=INPUT_SIZE, gray=True, normalization=True, flatten=False)


# TODO 모델에 따라 추가적인 preprocessing 필요한 경우 있음, data_loader.py에 가서 추가적인 전처리 필요 

# 모델 정의
model = models.Sequential([
    layers.Input(shape=(INPUT_SIZE, INPUT_SIZE, 1)),  # 그레이스케일 이미지
    layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2, 2)),
    
    layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2, 2)),
    
    layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
    layers.BatchNormalization(),
    layers.MaxPooling2D((2, 2)),
    
    layers.Flatten(),
    layers.Dense(256, activation='relu'),
    layers.Dropout(0.5),
    layers.Dense(NUM_CLASSES, activation='softmax')
])

model.summary()  

best_val_accuracy = 0
best_model = None
best_history = None
best_params = None

# Grid Search
# TODO 추가한 hyperparameter 만큼 반복문 추가
for lr in learning_rates:
    for opt_name in optimizers:
        for activation_name in activation_functions:
            
            train_ds = train_dataset.batch(BATCH_SIZE)
            train_ds = train_ds.prefetch(tf.data.AUTOTUNE)

            val_ds = validation_dataset.batch(BATCH_SIZE)
            val_ds = val_ds.prefetch(tf.data.AUTOTUNE)
            
            # 각 반복마다 새로운 모델 생성
            model = models.Sequential([
                layers.Input(shape=(INPUT_SIZE, INPUT_SIZE, 1)),  # 그레이스케일 이미지
                layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
                layers.BatchNormalization(),
                layers.MaxPooling2D((2, 2)),
                
                layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
                layers.BatchNormalization(),
                layers.MaxPooling2D((2, 2)),
                
                layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
                layers.BatchNormalization(),
                layers.MaxPooling2D((2, 2)),
                
                layers.Flatten(),
                layers.Dense(256, activation='relu'),
                layers.Dropout(0.5),
                layers.Dense(NUM_CLASSES, activation='softmax')
            ])
            
             # optimizer 설정
            if opt_name == 'adam':
                optimizer = tf.keras.optimizers.Adam(learning_rate=lr)
            else:
                optimizer = tf.keras.optimizers.SGD(learning_rate=lr, momentum=0.9)
            
            # 모델 컴파일, 손실함수 설정
            model.compile(
                optimizer=optimizer,
                loss = focal_loss_sparse(),
                metrics=['accuracy', tf.keras.metrics.SparseTopKCategoricalAccuracy(k=2)]
            )
            
            early_stopping = tf.keras.callbacks.EarlyStopping(
                monitor='val_accuracy',
                patience=5,
                restore_best_weights=True
            )
            
            history = model.fit(
                train_ds,
                epochs=EPOCHS,
                validation_data=val_ds,
                callbacks=[early_stopping],
                verbose=1
            )
            
            # validation 데이터에서 정확도 계산
            val_metrics = model.evaluate(val_ds)
            val_accuracy = val_metrics[1]  # accuracy는 두 번째 메트릭
            
            if val_accuracy > best_val_accuracy:
                best_val_accuracy = val_accuracy
                best_model = model
                best_history = history.history
                
                # TODO hyperparameter 추가
                best_params = {'learning_rate': lr, 'optimizer': opt_name, 'activation': activation_name}

print(f"\n최적 파라미터: {best_params}")
print(f"최고 검증 정확도: {best_val_accuracy:.4f}")

# 결과 시각화
plt.figure(figsize=(10, 6))
plt.plot(best_history['accuracy'], label='Training Accuracy')
plt.plot(best_history['val_accuracy'], label='Validation Accuracy')
plt.xlabel('Epochs')
plt.ylabel('Accuracy')
plt.title('Training and Validation Accuracy')
plt.legend()
plt.grid(True)
plt.show()

# Top-2 Accuracy 그래프
plt.figure(figsize=(10, 6))
plt.plot(best_history['sparse_top_k_categorical_accuracy'], label='Training Top-2 Accuracy')
plt.plot(best_history['val_sparse_top_k_categorical_accuracy'], label='Validation Top-2 Accuracy')
plt.xlabel('Epochs')
plt.ylabel('Top-2 Accuracy')
plt.title('Training and Validation Top-2 Accuracy')
plt.legend()
plt.grid(True)
plt.show()

# Classification Report 생성 및 시각화
report_dict = classification_report(y_true, y_pred, target_names=classes, output_dict=True)
df = pd.DataFrame(report_dict).transpose()

# 테이블 시각화
plt.figure(figsize=(12, 8))
plt.axis('off')
table = plt.table(cellText=df.values.round(3),
                 rowLabels=df.index,
                 colLabels=df.columns,
                 cellLoc='center',
                 loc='center',
                 bbox=[0.1, 0, 0.9, 1])

# 테이블 스타일 조정
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.2, 1.8)

plt.title('Classification Report', pad=20, size=15)
plt.tight_layout()
plt.savefig('classification_report_table.png', dpi=300, bbox_inches='tight')
plt.show()

# Confusion Matrix 계산을 위한 수정
y_true = []
y_pred = []

# 전체 validation 데이터셋에서 예측값과 실제값 수집
for images, labels in validation_dataset:
    # 예측
    predictions = best_model.predict(images, batch_size=BATCH_SIZE)
    
    # 예측값과 실제값을 리스트에 추가
    y_pred.extend(np.argmax(predictions, axis=1))
    y_true.extend(np.argmax(labels, axis=1))

# 혼동 행렬 (Confusion Matrix) 계산
cm = confusion_matrix(y_true, y_pred)

# Confusion Matrix 디스플레이
disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=classes)
disp.plot(cmap=plt.cm.Blues)
plt.title('Confusion Matrix')
plt.show()


