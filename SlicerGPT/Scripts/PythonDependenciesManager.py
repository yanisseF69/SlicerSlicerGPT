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
      import llama_cpp
      import faiss
      import fastapi
      import uvicorn
      import azure
      import ollama

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
      
      import platform

      if platform.system() == "Linux":
          import shutil

          gcc_path = shutil.which('gcc')
          gxx_path = shutil.which('g++')
          if not gcc_path:
            gcc_path = shutil.which('clang')
          if not gxx_path:
              gxx_path = shutil.which('clang++')
              
          env_vars = {
              'CC': gcc_path,
              'CXX': gxx_path,
              'CMAKE_C_COMPILER': gcc_path,
              'CMAKE_CXX_COMPILER': gxx_path
          }

          for key, value in env_vars.items():
              os.environ[key] = value


      os.environ["CMAKE_ARGS"] = "-DGGML_BLAS=on"
      os.environ["DGGML_BLAS_VENDOR"] = "OpenBLAS"
      os.environ["FORCE_CMAKE"] = "1"

      for dep in ["llama-cpp-python", "fastapi", "uvicorn", "langchain_huggingface", "langchain_community", "hf-xet", "faiss-cpu==1.7.4", "azure-ai-inference", "ollama"]:
        progressDialog.labelText = "Installing " + dep
        slicer.util.pip_install(dep)
    except Exception as e:
      error = f"Installation failed due to {str(e)}.\nIf the installation of llama_cpp failed, please ensure you have a C compiler installed."
      progressDialog.labelText = error
      raise InstallationError(error)