######################
# Import libraries
######################
import streamlit as st
import tensorflow as tf
import pandas as pd
import functions as fnc
import io

from tensorflow import keras
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import Embedding
from keras.layers import SimpleRNN
from keras.layers import LSTM
from keras.layers import GRU

import callbacks

######################
# Page Title
######################

st.write("""
# Sentiment Analysis with Keras
This app allows users to **build** and **train** their own model for sentiment analysis using Keras. Users can **customize the network architecture**, **manage datasets**, and **train** and **evaluate** their model.
***
""")

######################
# Session States
######################

states = [
    'file',
    'df',
    'column_X',
    'column_y',
    'train_set',
    'test_set',
    'table',
    'test_train_split',
    'batch_size',
    'vocab_size',
    'num_oov_buckets',
    'progress_prep',
    'encoded_train_set',
    'model',
    'model_built',
    'model_compiled',
    'history',
    'loss',
    'accuracy',
    'tf_text',
]

for state in states:
    if state not in st.session_state:
        st.session_state[state] = None

######################
# Upload Dataset
######################

st.header('Upload Your Dataset')
st.session_state['file'] = st.file_uploader("Select a file from you hard drive")
if st.session_state['file']:
    st.session_state['df'] = pd.read_csv(st.session_state['file'])
    buffer = io.StringIO()
    st.session_state['df'].info(buf=buffer)
    s = buffer.getvalue()
    st.text(s)
    st.warning("""
    When preparing a dataset for binary sentiment analysis, please keep in mind that your dataset must contain a column with text and a column with labels that can be binary encoded (e.g. positive and negative). 
    Additionally, your text and labels should not contain null-values. 
    Please ensure that your dataset meets these requirements before using it to train a binary sentiment analysis model.
    """)
    st.write("""
    ***
    """)

######################
# Preprocessing
######################

if st.session_state['file']:
    st.header('Preprocess Your Dataset')
    st.write("""
    The expected input format for the training data is a list of reviews, where each review is represented as an **array of integers**. 
    
    During preprocessing, all **punctuation** is removed, words are converted to **lowercase**, and **split by spaces**. The words are then **indexed by frequency**, with low integers representing frequent words. Additionally, there are three special tokens: **0** represents padding, **1** represents the start-of-sequence (SOS) token, and **2** represents unknown words.
    """)
    
    col1, col2 = st.columns(2)
    columns = list(st.session_state['df'].columns.values)
    st.session_state['column_X'] = col1.multiselect('Select Input Column', columns)
    st.session_state['column_y'] = col2.multiselect('Select Label Column', columns)
    if len(st.session_state['column_X']) > 1 or len(st.session_state['column_y']) > 1:
        st.warning('Please ensure that you select only one column for the input text and one column for the labels. Using multiple columns for either the input text or the labels may result in errors or unexpected behavior in your analysis or model.')
    
    col3, col4 = st.columns(2)
    st.session_state['test_train_split'] = col3.slider('Test Train Split', 0.1, 0.9, step=0.1, value=(0.5))
    st.session_state['batch_size'] = col4.select_slider('Batch Size', options=[16, 32, 64, 128, 256, 512, 1024, 2048], value=(32))

    col5, col6 = st.columns(2)
    st.session_state['vocab_size'] = col5.number_input('Vocabulary Size', step=1)
    st.session_state['num_oov_buckets'] = col6.number_input('Number of OOV Buckets', step=1)
    
    if st.button('Start Preprocessing'):
        df = st.session_state['df']
        column_X = st.session_state['column_X'][0]
        column_y = st.session_state['column_y'][0]
        test_train_split = st.session_state['test_train_split']
        batch_size = int(st.session_state['batch_size'])
        vocab_size = int(st.session_state['vocab_size'])
        num_oov_buckets = int(st.session_state['num_oov_buckets'])
        # progress
        prep_bar = st.progress(0)
        # encode labels
        df = fnc.encode_labels(df, column_y)
        # split
        train_len = round(len(df) * test_train_split)
        st.session_state['train_set'] = df[:train_len]
        st.session_state['test_set'] = df[train_len:]
        # tensorflow
        train_set = st.session_state['train_set']
        test_set = st.session_state['test_set']
        train_set = fnc.create_tensorflow_dataset(train_set, column_X, column_y)
        test_set = fnc.create_tensorflow_dataset(test_set, column_X, column_y)
        # vocabulary
        prep_bar.progress(40)
        vocabulary = fnc.create_vocabulary(train_set, batch_size, vocab_size)
        prep_bar.progress(60)
        st.session_state['table'] = fnc.create_lookup_table(vocabulary, num_oov_buckets)
        # data transformation
        prep_bar.progress(80)
        table = st.session_state['table']
        # encode train set
        encoded_train_set = train_set.batch(batch_size).map(fnc.preprocess)
        encoded_train_set = encoded_train_set.map(lambda x, y: fnc.encode_words(x, y, table)).prefetch(1)
        st.session_state['encoded_train_set'] = encoded_train_set
        # encode test set
        encoded_test_set = test_set.batch(batch_size).map(fnc.preprocess)
        encoded_test_set = encoded_test_set.map(lambda x, y: fnc.encode_words(x, y, table)).prefetch(1)
        st.session_state['encoded_test_set'] = encoded_test_set

        prep_bar.progress(100)
    if st.session_state['encoded_train_set']:
        st.write('Train: ', st.session_state['encoded_train_set'])
        st.write('Test: ', st.session_state['encoded_test_set'])
    
    st.write("""
    ***
    """)

######################
# Build Model
######################

if st.session_state['encoded_train_set']:
    st.header('Build Your Model')
    st.write("""
    You can add or remove layers by clicking on the (+) and (-) buttons, and each layer is displayed with a dropdown menu of **available layer types** (e.g., Dense, LSTM) and **input parameters** specific to that type.
    
    Once you have selected and configured your desired layers, you can click on the "Build Model" button to generate a **Sequential model** using the **Keras API**.
    """)

    if "model_layers" not in st.session_state:
        st.session_state["model_layers"] = []
    if "info_dict" not in st.session_state:
        st.session_state["info_dict"] = {}

    col1, col2 = st.columns([.05,1])
    with col1:
        if st.button('+'):
            st.session_state.model_layers.append("Layer")
    with col2:
        if st.button('-') and len(st.session_state.model_layers) > 0:
            st.session_state.model_layers.pop()
            st.session_state["info_dict"].popitem()
    
    layer_options = [
        'Dense Layer',
        'Embedding Layer',
        'Simple Recurrent Neural Network Layer',
        'Long Short-Term Memory Layer',
        'Gated Recurrent Unit Layer'
        ]
    input_dim = st.session_state['vocab_size'] + st.session_state['num_oov_buckets']
    
    for i, layer in enumerate(st.session_state.model_layers):
        layer_number = i + 1
        st.write(f'#### Layer {layer_number}')
        st.session_state['model_layers'][i] = st.selectbox('Select Layer', layer_options, key=f'select_layer_{layer_number}')
        infos = fnc.create_infos(st.session_state['model_layers'][i], layer_number, input_dim)
        st.session_state["info_dict"][layer_number] = infos
    
    if len(st.session_state["info_dict"]) >= 1:
        if st.button('Build Model'):
            layer_dict = {'Dense': Dense, 'Embedding': Embedding, 'SimpleRNN': SimpleRNN, 'LSTM': LSTM, 'GRU': GRU}
            st.session_state["model"] = Sequential()
            for layer in st.session_state["info_dict"]:
                layer_type = st.session_state["info_dict"][layer]['layer']
                layer_class = layer_dict[layer_type]
                hyper_params = {k: v for i, (k, v) in enumerate(st.session_state["info_dict"][layer].items()) if i != 0}
                st.session_state["model"].add(layer_class(**hyper_params))
                st.session_state["model"].build()
            st.session_state['model_built'] = True
    else:
        st.warning('You must add at least one layer to the model before you can build it!')
    
    if st.session_state['model_built']:
        st.success('The model was built successfully!')
    st.write("""
    ***
    """)


######################
# Compile Model
######################

if st.session_state['model_built']:
    st.header('Compile Your Model')
    st.write("""
    The process of compiling the model involves specifying the **loss function**, **optimizer**, and **evaluation metrics** that will be utilized to train and evaluate the model throughout the training process.
    
    Different combinations of optimizers, loss functions, and metrics can have a significant impact on the performance of the model, so it's important to **choose these hyperparameters carefully** and optimize them for the specific task at hand.
    """)

    optimizers = [
        'sgd',
        'rmsprop',
        'adagrad',
        'adadelta',
        'adam',
        'adamax',
        'nadam',
        'ftrl'
    ]
    loss_functions = [
        'mean_squared_error',
        'mean_absolute_error',
        'mean_absolute_percentage_error',
        'mean_squared_logarithmic_error',
        'categorical_crossentropy',
        'sparse_categorical_crossentropy',
        'binary_crossentropy',
        'hinge',
        'squared_hinge',
        'cosine_similarity',
        'poisson',
        'kullback_leibler_divergence',
    ]
    metrics = [
        'accuracy',
        'mse',
        'mae',
        'mape',
        'precision',
        'recall',
        'AUC',
        'f1_score',
    ]

    col1, col2 = st.columns(2)
    optimizer = col1.selectbox('Optimizer', optimizers, index=4)
    loss_function = col2.selectbox('Loss Function', loss_functions, index=6)
    metrics = st.multiselect('Metrics', metrics)

    if st.button('Compile Model'):
        st.session_state["model"].compile(loss=loss_function, optimizer=optimizer, metrics=metrics)
        st.session_state["model_compiled"] = True

    if st.session_state["model_compiled"]:
        with st.expander('Summary'):
            st.session_state["model"].summary(line_length=79, print_fn=lambda x: st.text(x))
        st.success('The model was compiled successfully!')

    st.write("""
    ***
    """)


######################
# Train Model
######################

if st.session_state["model_compiled"]:
    st.header('Train Your Model')
    st.write("""
    After compiling the model, you can **specifying the number of epochs** and then train your model on the labeled training dataset.

    During each epoch, the model is fed the entire training dataset in small batches, and the weights and biases of the model are adjusted to **minimize the loss function**. Typically, **multiple epochs are needed** to achieve good performance on the training dataset, but too many epochs can lead to overfitting, where the model performs well on the training data but poorly on new, unseen data.
    """)

    train_set = st.session_state['encoded_train_set']
    num_epochs = st.number_input('Epochs', step=1)

    if st.button('Train Model'):
        st.session_state['history'] = st.session_state["model"].fit(train_set, epochs=num_epochs, callbacks=[callbacks.StreamlitCallback(num_epochs)])

    if st.session_state['history']:
        st.success('The model was trained successfully!')

    st.write("""
    ***
    """)


######################
# Evaluate Model
######################

if st.session_state['history']:
    st.header('Evaluate Your Model')
    st.write("""
    Write something here! 
    """)
    
    if st.session_state['loss'] == None and st.session_state['accuracy'] == None:
        loss, accuracy = st.session_state["model"].evaluate(st.session_state['encoded_test_set'])
        st.session_state['loss'] = loss
        st.session_state['accuracy'] = accuracy
    
    loss_str = f"Loss: {st.session_state['loss']}"
    accuracy_str = f"Accuracy: {st.session_state['accuracy']}"
    st.text(loss_str)
    st.text(accuracy_str)

    st.write("""
    ***
    """)


######################
# Inference
######################

if st.session_state['history']:
    st.header('Inference')
    st.write("""
    Machine learning inference is the stage in the development process where the knowledge acquired by the neural network during training is applied. The trained model is utilized to **make predictions** or inferences on **new** and **previously unseen data**. 
    """)

    text = st.text_area('Write something and let your model predict the sentiment.')
    if text:
        st.session_state['tf_text'] = fnc.inf_preprocessing(text)

    if st.button('Predict Sentiment'):
        result = st.session_state['model'].predict(st.session_state['tf_text'])
        percentage = round(result[0][0] * 100)
        result_str = f'Your text has a {percentage}% probability of being positive.'
        st.info(result_str)
