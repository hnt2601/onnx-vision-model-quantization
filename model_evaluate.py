import torch
import torchvision as tv
import onnxruntime
import numpy as np
import random

from tqdm import tqdm
from torch.utils.data import DataLoader
from common import MEAN, STD


def seed_worker(worker_id):
    worker_seed = torch.initial_seed() % 2**32
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    torch.manual_seed(worker_seed)
    torch.cuda.manual_seed(worker_seed)
    torch.cuda.manual_seed_all(worker_seed)


def accuracy(true_labels, predicted_labels):
    correct_predictions = sum(
        1 for true, predicted in zip(true_labels, predicted_labels) if true == predicted
    )
    total_predictions = len(true_labels)
    accuracy = correct_predictions / total_predictions

    return accuracy


def evaluate(test_set, model_path, batch_size=1):

    g = torch.Generator()
    g.manual_seed(2147483647)

    test_loader = DataLoader(test_set, batch_size=batch_size, shuffle=True, drop_last=True, worker_init_fn=seed_worker, generator=g)
    
    pbar = tqdm(total=len(test_loader))

    ort_inputs = {}
    true_labels = []
    predicted_labels = []

    # Create an ONNX Runtime session with GPU as the execution provider
    options = onnxruntime.SessionOptions()
    options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    # options.log_severity_level = 3  # Set log verbosity to see GPU provider details
    sess = onnxruntime.InferenceSession(
        model_path, providers=["CUDAExecutionProvider", "CPUExecutionProvider"], sess_options=options
    )

    # Check the input and output names and shapes of the model
    input_name = sess.get_inputs()[0].name
    # output_name = sess.get_outputs()[0].name
    # input_shape = sess.get_inputs()[0].shape
    # output_shape = sess.get_outputs()[0].shape
    # print(f"Input name: {input_name}, Input shape: {input_shape}")
    # print(f"Output name: {output_name}, Output shape: {output_shape}")

    
    for inputs, labels in test_loader:
        try:
            inp_list = [inp.numpy() for inp in inputs]
            inps = np.stack(inp_list, axis=0)

            ort_inputs.update({input_name: inps})

            predictions = sess.run(None, ort_inputs)[0]

            for i in range(0, batch_size):
                pred_label = np.argmax(predictions[i], axis=0)
                true_label = labels[i].numpy()

                true_labels.append(true_label)
                predicted_labels.append(pred_label)

            pbar.update(1)
        except Exception as e:
            print(e)
            continue

    pbar.close()

    acc = accuracy(true_labels, predicted_labels)

    del sess

    return acc


if __name__ == "__main__":
    import os
    import onnx
    
    # os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    
    data_path = "/media/data/hoangnt/Projects/Datasets"
    int8_model_path = "pretrained/efficientnetv2_rw_t_quant_0.onnx"
    int8_model = onnx.load(int8_model_path)
    batch_size = 1024

    transform = tv.transforms.Compose(
        [tv.transforms.ToTensor(),
         tv.transforms.Normalize(MEAN, STD)]
    )
    
    dataset = tv.datasets.CIFAR10(
        root=data_path,
        train=False,
        download=False,
        transform=transform,
    )

    i = 0
    while (i < 2):

        g = torch.Generator()
        g.manual_seed(2147483647)
        
        int8_acc = evaluate(dataset, int8_model_path, batch_size)
    
        print(int8_acc)

        i += 1