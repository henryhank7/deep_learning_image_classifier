import torch   #imports PyTorch
from torchvision import transforms, datasets # imports transforms functions which let me transform/edit the pictures
from torch import nn, optim
import torch.nn.functional as F
from torchvision import models
import json
from PIL import Image


class model_classifier(nn.Module):
    def __init__(self, hidden_units):
        super().__init__()
        self.fc1 = nn.Linear(hidden_units, 1656)
        self.fc2 = nn.Linear(1656, 1242)
        self.fc3 = nn.Linear(1242, 1000)

        self.dropout = nn.Dropout(p=0.2)

    def forward(self, x):

        x = x.view(x.shape[0], -1)

        x = self.dropout(F.relu(self.fc1(x)))
        x = self.dropout(F.relu(self.fc2(x)))


        x = F.log_softmax(self.fc3(x), dim = 1)

        return x


def create_model(imagenet, learning_rate, hidden_units, epochs, device):
    ''' Creates a fully trained neural network
    
    Parameters
    ----------
    
    imagenet:       string
                    The name of the imagenet model that you want to use to setup your features for your classifier (Eg: densenet161)
    learning_rate:  float
                    the learning rate used in your optimizer
    hidden_units:   int
                    the number of hidden units in the input layer of your Neural Network
    epochs:         int
                    number of epochs used during the training/validation pass.
    device:         torch.device
                    should be 'cuda' or 'cpu', train.py detects this for you after the user inputs his preference
    
    Returns
    -------
    
    fully trained model given parameters. model is also saved every 5 epochs to conserve state incase it overfits
    
    Notes
    -----
    The function locks the model's parameters and only works on the classifier.
    
    Negative log likelihood loss is used
    
    Stochastic Gradient Descent is used as the optimizer.
    
    dataloader is created in another function called load_data(...)
    
    model is trained in a different function called train_model(...)
    
    '''
    
    model = models.densenet161(pretrained=True) 
    #need to create the model or else the code bugs out at the next line, model gets overwritten
    exec("model = models.{}(pretrained=True)".format(imagenet))

    for param in model.parameters():
        param.requires_grad = False

    classifier = model_classifier(hidden_units)
    model.classifier = classifier
    model.to(device)

    criterion = nn.NLLLoss()
    optimizer = optim.SGD(model.classifier.parameters(), lr = learning_rate)

    main_dir = 'flowers'
    
    dataloaders = load_data(main_dir)
    
    model = train_model(model, dataloaders, criterion, optimizer, epochs, device, imagenet)
    
    print('Complete')
    return model


def train_model(model, dataloaders, criterion, optimizer, epochs, device, imagenet):
    ''' This function trains the classifier using backpropagation
    
    Parameters
    ----------
    
    model:          model with parameters from create_model(...) function
    
    dataloaders:    dict.
                    dictionary containing the dataloader for train, validate and test
    criterion:      cost function criterion used during the backward pass process
    
    optimizer:      optimizer used to update the weights, created in create_model(...) function
    
    epochs:         int
                    number of epochs used during the training/validation pass.
    device:         torch.device
                    should be 'cuda' or 'cpu', train.py detects this for you after the user inputs his preference
    imagenet:       string
                    imagenet name, used during the save process to differentiate different models (Eg: densenet161)
                    
    '''
    
    print(device)
    test_losses, train_losses, test_accuracy =[], [], []
    save_every = 5
    
    for epoch in range(0,epochs):
        running_loss = 0
        for inputs, labels in dataloaders['train']:
            inputs, labels = inputs.to(device), labels.to(device)

            optimizer.zero_grad()

            outputs = model.forward(inputs)
            loss = criterion(outputs,labels)
            loss.backward()

            optimizer.step()

            running_loss += loss.item()

        else:

            model.eval() #turning off dropout
            test_loss = 0
            accuracy = 0
                # Turning off gradients for validation to reduce memroy and computations
            with torch.no_grad():
                for ii, (images, labels) in enumerate(dataloaders['validate']):
                    images, labels = images.to(device), labels.to(device)

                    valid_output = model(images)
                    test_loss += criterion(valid_output, labels)

                    prob = torch.exp(valid_output)
                    top_p, top_class = prob.topk(1, dim=1)
                    if ii == 0:
                        equals = top_class == labels.view(*top_class.shape)
                    else:
                        equals = torch.cat((equals,top_class == labels.view(*top_class.shape)))

            accuracy = torch.mean(equals.type(torch.FloatTensor))

            train_losses.append(running_loss/len(dataloaders['train']))
            test_losses.append(test_loss/len(dataloaders['validate']))
            test_accuracy.append(accuracy)

            model.train()

            print("Epoch: {}/{}.. ".format(epoch+1, epochs),
                  "Training Loss: {:.3f}.. ".format(running_loss/len(dataloaders['train'])),
                  "Test Loss: {:.3f}.. ".format(test_loss/len(dataloaders['validate'])),
                  "Test Accuracy: {:.3f}".format(accuracy))

        if (epoch + 1) % save_every ==0:
            state = {'epoch': epoch,
                     'state_dict': model.state_dict(),
                     'optimizer':optimizer.state_dict()
                     }

            filepath = 'model_project_' + str(epoch+1) +'imagenet' + '.pth'
            torch.save(state, filepath)
        
    save_model(model, epoch, optimizer)
    
    return model

def save_model(model, epoch, optimizer):
    ''' Saves the final model after all epochs
    
    Parameters
    ----------
    model:  the current model and it's architecture
    
    epoch:  int
            the number of epochs - 1 (ie: for 25 passes epochs will be 24)
        
    optimizer: optimizer used to update the weights
    
    Notes
    -----
    
    The model's state is saved as well as the optimizer's state. These are saved to resume and continue training
    sometime in the future.
    
    '''
    # state_dict:     dictioanry containing the model's state (architecture + tensors)

    state = {'epoch': epoch,
             'state_dict': model.state_dict(),
             'optimizer':optimizer.state_dict()
            }
    
    filepath = 'final_model.pth'
    torch.save(state, filepath)
    
    return


def load_data(main_dir):
    ''' Returns a dictionary containing the dataloader for the training, validation and testing data
    
    Parameters
    ----------
    
    main_dir:   your operating system's directory containing the 'train', 'valid' and 'test' directories which contain the images
    
    Notes
    -----
    Performs the standard image transformations.
              
    '''
    train_dir = main_dir + '/train'
    valid_dir = main_dir + '/valid'
    test_dir  = main_dir + '/test'
    train_transforms = transforms.Compose([transforms.RandomRotation(30),
                                       transforms.RandomResizedCrop(224),
                                       transforms.RandomHorizontalFlip(),
                                       transforms.ToTensor(),
                                       transforms.Normalize([0.485,0.456,0.406],
                                                            [0.229,0.224,0.225])])

    test_transforms = transforms.Compose([transforms.RandomResizedCrop(224),
                                      transforms.ToTensor(),
                                      transforms.Normalize([0.485,0.456,0.406],
                                                           [0.229,0.224,0.225])])


    # TODO: Load the datasets with ImageFolder
    train_dataset_imgs = datasets.ImageFolder(train_dir, transform = train_transforms)
    valid_dataset_imgs = datasets.ImageFolder(valid_dir, transform = test_transforms)
    test_dataset_imgs  = datasets.ImageFolder(test_dir,  transform = test_transforms)

# TODO: Using the image datasets and the trainforms, define the dataloaders
    dataloaders = {'train': torch.utils.data.DataLoader(train_dataset_imgs, batch_size = 64, shuffle=True),
               'validate': torch.utils.data.DataLoader(valid_dataset_imgs, batch_size = 64, shuffle=True),
               'test': torch.utils.data.DataLoader(test_dataset_imgs, batch_size = 64, shuffle=False)}

    return dataloaders

def load_model(filepath, hidden_units ,imagenet):
    ''' Returns a model after having loaded the saved PyTorch (.pth) model. Model can be used for predictions
    
    Parameters
    ----------
    
    filepath:       filepath for the model (eg. final_model.pth)
                    pass the directory and file name for the saved model
    hidden_units:   int
                    number of hidden units in the input layer for the classifier
    imagenet:       string
                    imagenet name, needs to be given by user for PyTorch to load the proper architecture    
                                    
    Notes
    -----
    
    If no imagenet is given, then the densenet161 is assumed
    
    model name is printed
    '''
    print(imagenet)
    model = models.densenet161(pretrained=True)
    
    if imagenet != 'densenet161' :
        exec("model = models.{}(pretrained=True)".format(imagenet))
    
    state = torch.load(filepath)
    model.classifier = model_classifier(hidden_units)
    model.load_state_dict(state['state_dict'])
    
    for param in model.parameters():
        param.requires_grad = False
    
    return model

def process_image(image_path):
    ''' Scales, crops, and normalizes a PIL image for a PyTorch model,
        returns a PyTorch tensor.
    
    Parameters
    ----------
    
    image_path: directory + name of the image    (eg: 'flowers/test/40/image_04568.jpg')
    
    '''
    
    
    image_pil = Image.open(image_path)
    
    transformations = transforms.Compose([transforms.Resize(256),
                                          transforms.CenterCrop(224),
                                          transforms.ToTensor(),
                                          transforms.Normalize([0.485,0.456,0.406],
                                                            [0.229,0.224,0.225])])
    
    transformed = transformations(image_pil)
    
    return transformed


def predict(image_path, model, device, json_path,  topk = 5):
    ''' Predict the class (or classes) of an image using a trained deep learning model.
    
    Paramters
    ---------
    
    image_path:     directory + name of the image    (eg: 'flowers/test/40/image_04568.jpg')
    
    model:          deep learning PyTorch model
    
    device:         torch.device
                    should be 'cuda' or 'cpu', to specify where the predictions are made

    json_path:      directory + name of json file that relates predicted classes to labels

    topk :          int
                    top n classes for probabilities and label predictions. Defaults to 5 but can specified by the user.     
    
    '''

    transformed = process_image(image_path)
    transformed = transformed.unsqueeze(0)
    transformed = transformed.to(device)
    transformed.to(device)
    model.to(device)
    model.eval()
    
    with torch.no_grad():
        output = model(transformed)
        probabilities = torch.exp(output)
        top_p, top_class = probabilities.topk(topk, dim =1)
    
    names = []
    
    with open(json_path, 'r') as f:
        cat_to_name = json.load(f)
    
    #need to convert to 'cpu' or else we get an error if its on the GPU, error is that .numpy() doesn't work on GPU
    top_class = top_class.to('cpu').numpy()
    top_p = top_p.to('cpu').numpy()
    for i in top_class[0]:
        names.append(cat_to_name[str(i)])
    
    #returning a numpy array for the probabilities
    return top_p, names    