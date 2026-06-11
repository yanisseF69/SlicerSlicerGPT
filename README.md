# SlicerGPT: Chatbot Extension for 3D Slicer

<img src="https://github.com/yanisseF69/SlicerSlicerGPT/blob/main/SlicerGPT/Resources/Screenshots/App.png" alt="App screenshot"/>

## Table of contents

* [Introduction](#introduction)
* [Requirements](#requirements)
* [Installation & Usage](#installation--usage)
* [First Launch (one-time setup)](#first-launch-one-time-setup)
* [Model download](#model-download)
* [Starting the Chatbot](#starting-the-chatbot)
* [Using SlicerGPT](#using-slicergpt)
* [Subsequent Launches](#subsequent-launches)

## Introduction

**SlicerGPT** is an extension for [3D Slicer](https://www.slicer.org/) that integrates a large language model (LLM) directly into the Slicer environment to assist users with 3D Slicer usage.

This extension leverages a **Retrieval-Augmented Generation (RAG)** architecture that combines:

- The active **MRML Scene** (Medical Reality Markup Language), providing the LLM with contextual information about loaded nodes, volumes, and modules in the current session.
- A **FAISS vector store**, which contains:
  - Official Slicer documentation.
  - Python and Markdown files from tutorials, examples, and community extensions.
  - Forum questions and answers, especially from [Slicer Discourse](https://discourse.slicer.org/).

By combining the live scene context with relevant textual knowledge, **SlicerGPT** can generate actionable, context-aware responses to help users navigate and automate 3D Slicer more effectively—even without deep programming experience.

## Requirements

SlicerGPT relies on the [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) library to run the LLM locally. Therefore, a proper C/C++ compiler is required on your system to build the underlying `llama.cpp` backend.

You can find full installation instructions and platform-specific compiler requirements in the official GitHub repository:  
👉 [https://github.com/abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
For the moment, only the CPU version is compatible with this extension.

In addition, SlicerGPT also requires [Ollama](https://ollama.com/) to be installed on your computer. Ollama is used to manage and run the local LLM models in a convenient way, and SlicerGPT connects to it as a backend. Make sure Ollama is installed and running in the background before using the extension.
You can install it by following this link 👉 [https://ollama.com/download](https://ollama.com/download)

Make sure your 3D Slicer's python version is 3.8 or higher.

## Installation & Usage

<img src="https://github.com/yanisseF69/SlicerSlicerGPT/blob/main/SlicerGPT/Resources/Screenshots/Installation.png" alt="Installation screenshot"/>

Once SlicerGPT is installed as a 3D Slicer extension, follow these steps to get it running correctly.

### First Launch (one-time setup)

When launching **SlicerGPT for the first time**, the extension will:

1. **Install Python dependencies**, including:
   - `llama-cpp-python`
   - `faiss-cpu==1.7.4`
   - `ollama`
   - Other required libraries

2. **Automatically restart 3D Slicer** once dependencies are installed.

/!\ **Important:** This first-time setup is automated, but may take a few minutes depending on your system and internet speed.

---

### Model Download

After restarting, when you launch the extension again:

- SlicerGPT will **download and prepare the LLM model** used for generating responses.
- This step is **also automatic**, but can take several minutes the first time (especially on slow connections or older hardware).
- The model will be cached locally for future use.

---

### Starting the Chatbot

Once the model is loaded, SlicerGPT will start a local web server using [Uvicorn](https://www.uvicorn.org/), which powers the backend communication between the chatbot and Slicer.

When the server is fully running, and the chatbot is ready to receive input.

---

### Using SlicerGPT

- You can now interact with the chatbot inside 3D Slicer via its panel.
- Ask questions related to:
  - Your current MRML scene
  - Python scripting
  - Module usage
  - Troubleshooting
- The LLM will answer using contextual information from your scene and a large collection of documentation, code, and forum content.

---

### Subsequent Launches

After the initial setup:
- Dependencies and model will be reused from cache.
- SlicerGPT will start much faster.
