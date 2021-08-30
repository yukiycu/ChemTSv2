import argparse
import os
import sys

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Embedding, GRU, TimeDistributed
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.preprocessing import sequence
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import yaml

sys.path.append("../")
from utils.make_smiles import zinc_data_with_bracket_original, zinc_processed_with_bracket


def get_parser():
    parser = argparse.ArgumentParser(
        description="",
        usage=f"python {os.path.basename(__file__)} -c CONFIG_FILE"
    )
    parser.add_argument(
        "-c", "--config", type=str, required=True,
        help="path to a config file"
    )
    return parser.parse_args()


def prepare_data(smiles, all_smile):
    all_smile_index = []
    for i in range(len(all_smile)):
        smile_index = []
        for j in range(len(all_smile[i])):
            smile_index.append(smiles.index(all_smile[i][j]))
        all_smile_index.append(smile_index)
    X_train = all_smile_index
    y_train = []
    for i in range(len(X_train)):
        x1 = X_train[i]
        x2 = x1[1:len(x1)]
        x2.append(0)
        y_train.append(x2)

    return X_train, y_train


def save_model(model, output, output_weight=None):
    model_json = model.to_json()
    with open(output, "w") as json_file:
        json_file.write(model_json)
    print(f"Saved model to {output}")
    if output_weight is not None:
        model.save_weights(output_weight)
        print(f"Saved model weights to {output_weight}")


def update_config(conf):
    conf.setdefault("dataset", "../data/250k_rndm_zinc_drugs_clean.smi")
    conf.setdefault('output_json', "../model/model.json")
    conf.setdefault('output_weight', "../model/model.h5")
    conf.setdefault('dropout_rate', 0.2)
    conf.setdefault('learning_rate', 0.01)
    conf.setdefault('epoch', 100)
    conf.setdefault('batch_size', 512)
    conf.setdefault('validation_split', 0.1)
    conf.setdefault('units', 256)    
    conf.setdefault('rec_dropout_rate', 0.2)
    conf.setdefault('maxlen', 82)


def plot_training_curve(result, conf):
    fname = f"learning_curve_GRU_{os.path.basename(conf['dataset']).split('.')[0]}_units{conf['units']}_dropout{conf['dropout_rate']}_recDP{conf['rec_dropout_rate']}_lr{conf['learning_rate']}_batchsize{conf['batch_size']}.png"
    plt.plot(range(1, len(result.history['accuracy']) + 1), result.history['accuracy'], label="training")
    plt.plot(range(1, len(result.history['val_accuracy']) + 1), result.history['val_accuracy'], label="validation")
    plt.xlabel('Epochs')
    plt.ylabel('Accuracy')
    plt.legend()
    plt.savefig(
        fname,
        dpi = 300,
        bbox_inches='tight', 
        pad_inches=0,)
    print(f"Training curve was saved to {fname}")


def main():
    args = get_parser()
    with open(args.config, "r") as f:
        conf = yaml.load(f)
    update_config(conf)
    print(f"========== Configuration ==========")
    for k, v in conf.items():
        print(f"{k}: {v}")
    print(f"===================================")

    smile = zinc_data_with_bracket_original(conf["dataset"])
    valcabulary, all_smile = zinc_processed_with_bracket(smile)
    print(f"vocabulary:\n{valcabulary}\n"
          f"size of SMILES list: {len(all_smile)}")
    X_train, y_train = prepare_data(valcabulary, all_smile) 
  
    X = sequence.pad_sequences(X_train, maxlen=conf['maxlen'], dtype='int32', padding='post', truncating='pre', value=0.)
    y = sequence.pad_sequences(y_train, maxlen=conf['maxlen'], dtype='int32', padding='post', truncating='pre', value=0.)
    
    y_train_one_hot = np.array([to_categorical(sent_label, num_classes=len(valcabulary)) for sent_label in y])
    print(f"shape of y_train_one_hot: {y_train_one_hot.shape}")

    # Build model
    model = Sequential()
    model.add(Embedding(input_dim=len(valcabulary), output_dim=len(valcabulary), input_length=X.shape[1], mask_zero=False))
    model.add(GRU(conf['units'], input_shape=(82,64), activation='tanh', dropout=conf['dropout_rate'], recurrent_dropout=conf['rec_dropout_rate'], return_sequences=True))
    model.add(GRU(conf['units'], activation='tanh', dropout=conf['dropout_rate'], recurrent_dropout=conf['rec_dropout_rate'], return_sequences=True))
    model.add(TimeDistributed(Dense(len(valcabulary), activation='softmax')))
    optimizer=Adam(learning_rate=conf['learning_rate'])
    model.summary()
    model.compile(loss='categorical_crossentropy', optimizer=optimizer, metrics=['accuracy'])

    if conf['epoch'] == -1:  # Check: No longer work
        early_stopping = EarlyStopping(monitor='val_loss', patience=5, verbose=1)
        checkpointer = ModelCheckpoint(filepath=conf['output_weight'], verbose=1, save_weights_only=True, save_best_only=True)
    result = model.fit(
        X, 
        y_train_one_hot,
        batch_size=conf['batch_size'],
        epochs=conf['epoch'],
        verbose=1,
        callbacks=[early_stopping, checkpointer] if conf['epoch'] == -1 else None,
        validation_split=conf['validation_split'],
        shuffle=True,)
    save_model(model, conf["output_json"])

    plot_training_curve(result, conf)


if __name__ == "__main__":
    main()
