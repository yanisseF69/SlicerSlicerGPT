import os
import slicer

class InstallationError(Exception):
  def __init__(self, message):
    super().__init__(message)
    self.message = message

class PythonDependencyChecker(object):
  """
  Class responsible for installing the Modules dependencies
  """

  @classmethod
  def areDependenciesSatisfied(cls):
    try:
      import langchain_huggingface
      import langchain_community
      import faiss
      import fastapi
      import uvicorn
      import azure
      import ollama
      import sentence_transformers
      import httptools
      import websockets

      return True

    except ImportError:
      return False

  @classmethod
  def installDependenciesIfNeeded(cls, progressDialog=None):
    if cls.areDependenciesSatisfied():
      return

    try:

      progressDialog = progressDialog or slicer.util.createProgressDialog(maximum=0)
      progressDialog.labelText = "Installing PyTorch"
      

      for dep in ["fastapi", "uvicorn", "langchain_huggingface", "langchain_community", "hf-xet", "faiss-cpu", "azure-ai-inference", "ollama", "sentence-transformers", "httptools", "websockets"]:
        progressDialog.labelText = "Installing " + dep
        slicer.util.pip_install(dep)
    except Exception as e:
      error = f"Installation failed due to {str(e)}.\nIf the installation of llama_cpp failed, please ensure you have a C compiler installed."
      progressDialog.labelText = error
      raise InstallationError(error)