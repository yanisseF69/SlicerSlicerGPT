import logging
import os
from typing import Annotated, Optional

import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

import qt

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

#
# SlicerGPT
#


class SlicerGPT(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = ("SlicerGPT")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Utilities")]
        self.parent.dependencies = []
        self.parent.contributors = ["Yanisse FERHAOUI (Institut Pascal & UCA & UCBL)"]
        self.parent.helpText = _("""
This module integrates an intelligent chatbot designed to assist 3D Slicer users.
You can ask questions in natural language about the software usage, Python scripting, extensions, or advanced features.
<br><br>
The chatbot uses a local knowledge base (RAG) including documentation, forum content, and source code to provide accurate answers.
<br><br>
See more information in the <a href="https://github.com/yanisseF69/SlicerSlicerGPT">module documentation</a>.
""")
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = _("""
This plugin was initially developed during Yanisse FERHAOUI's final-year internship as part of an academic research project.
""")


#
# SlicerGPTParameterNode
#


@parameterNodeWrapper
class SlicerGPTParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """

    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode


#
# SlicerGPTWidget
#


class SlicerGPTWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        if not self.areDependenciesSatisfied():
            error_msg = "Llama.cpp, langchain, azure AI inference and transformers are required by this plugin.\n" \
                        "Please click on the Download button to download and install these dependencies.\n" \
                        "IMPORTANT : Llama.cpp will be compiled after its installation, please ensure you have a C/C++ compiler installed in your computer."
            self.layout.addWidget(qt.QLabel(error_msg))
            downloadDependenciesButton = qt.QPushButton("Download dependencies and restart")
            downloadDependenciesButton.connect("clicked(bool)", self.downloadDependenciesAndRestart)
            downloadDependenciesButton.setCheckable(False)
            self.layout.addWidget(downloadDependenciesButton)
            self.layout.addStretch()
            return

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/SlicerGPT.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.

        self.logic = SlicerGPTLogic()
        self.loadingWidget = qt.QWidget()
        loadingLayout = qt.QVBoxLayout()
        loadingLabel = qt.QLabel("Launching local AI engine... Please wait.")
        loadingLabel.setAlignment(qt.Qt.AlignCenter)
        loadingLayout.addWidget(loadingLabel)
        self.loadingWidget.setLayout(loadingLayout)

        self.uiWidget = uiWidget
        self.ui = slicer.util.childWidgetVariables(self.uiWidget)

        self.stack = qt.QStackedWidget()
        self.stack.addWidget(self.loadingWidget)
        self.stack.addWidget(self.uiWidget)

        self.layout.addWidget(self.stack)

        self.stack.setCurrentIndex(0)

        self.logic.widget = self

        # Connections

        self.ui.prompt.textChanged.connect(self.onPromptTextChanged)

        # Buttons
        self.ui.prompt.enabled = True
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.thinkBox.toggled.connect(self.onThinkBoxToggled)

        self.ui.apiKeyButton.connect("clicked(bool)", self.onApiKeyInserted)

        self.ui.baseButton.clicked.connect(lambda: self.onModelsBoxChanged(self.ui.baseButton))
        self.ui.apiButton.clicked.connect(lambda: self.onModelsBoxChanged(self.ui.apiButton))
        self.ui.ollamaButton.clicked.connect(lambda: self.onModelsBoxChanged(self.ui.ollamaButton))

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        logging.info("Cleaning up SlicerGPT module")
        
        if hasattr(self, "logic") and hasattr(self.logic, "proc"):
            try:
                import requests
                requests.get("http://127.0.0.1:8081/shutdown", timeout=1.0)
                logging.info("Sent shutdown request to server")
            except:
                pass
            
            if self.logic.proc.state() == qt.QProcess.Running:
                logging.info("Terminating server process")
                
                self.logic.proc.terminate()
                
                if not self.logic.proc.waitForFinished(3000):
                    logging.warning("Server did not terminate gracefully, killing process")
                    self.logic.proc.kill()
                    
                    if not self.logic.proc.waitForFinished(2000):
                        logging.error("Failed to kill server process")
                    else:
                        logging.info("Server process killed")
                else:
                    logging.info("Server process terminated gracefully")
                    
                try:
                    pid = self.logic.proc.processId()
                    if pid > 0:
                        import os, signal
                        try:
                            os.kill(pid, signal.SIGTERM)
                            logging.info(f"Sent SIGTERM to process {pid}")
                        except:
                            pass
                except:
                    pass
            
            self.logic.proc.closeReadChannel(qt.QProcess.StandardOutput)
            self.logic.proc.closeReadChannel(qt.QProcess.StandardError)
            self.logic.proc.closeWriteChannel()
            
            logging.info("Process cleanup completed")
        
        if hasattr(self, "logic") and hasattr(self.logic, "proc"):
            self.logic.proc = None
        
        self.removeObservers()

    def onPromptTextChanged(self) -> None:
        """Called when the prompt text is changed."""
        if self.applyButtonEnabled:
            if self.ui.prompt.toPlainText():
                self.ui.applyButton.enabled = True
            else:
                self.ui.applyButton.enabled = False

    def onModelsBoxChanged(self, button) -> None:
        """Called when the user change the model used."""
        if button.text == "API Model":
            self.logic.setApi(True)
            self.logic.setOllama(False)
        elif button.text == "Ollama Model":
            self.logic.setOllama(True)
        else:
            self.logic.setApi(False)
            self.logic.setOllama(False)

    def onThinkBoxToggled(self, checked):
        self.logic.setThinking(checked)

    def onServerReady(self):
        self.stack.setCurrentIndex(1)
        self.applyButtonEnabled = True

    def onApiKeyInserted(self):
        """Insert the API key to the logic."""
        self.logic.addApiKey(self.ui.apiKeyText.text)
        self.ui.apiKeyText.clear()


    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            text = self.ui.prompt.toPlainText()
            self.ui.prompt.clear()
            message = {"role": "user", "content": text}
            self.ui.applyButton.enabled = False
            self.ui.apiKeyButton.enabled = False
            self.applyButtonEnabled = False
            dialogue = self.logic.process(message)
            self.ui.conversation.setText(dialogue)

    def updateConversation(self, dialogue_text):
        """
        Update the UI with the response generated.
        This method is called when the async request send a response.
        """
        self.ui.conversation.setText(dialogue_text)

        self.ui.conversation.moveCursor(qt.QTextCursor.End)
        self.ui.conversation.ensureCursorVisible()

        
        self.ui.apiKeyButton.enabled = True
        self.applyButtonEnabled = True

    def updateConversationLive(self, partial_text):
        html = markdown_to_html(partial_text)
        formatted = (
            f'<div style="text-align:right; margin: 5px;"><span style="color:blue; font-weight:bold;">You:</span><br>'
            f'{markdown_to_html(self.logic.dialogue[-2]["content"])}</div>'
            f'<div style="text-align:left; margin: 5px;"><span style="color:red; font-weight:bold;">SlicerGPT:</span><br>{html}</div>'
        )
        self.ui.conversation.setText(formatted)
        self.ui.conversation.moveCursor(qt.QTextCursor.End)
        self.ui.conversation.ensureCursorVisible()
    
    @staticmethod
    def areDependenciesSatisfied():
        from Scripts.PythonDependenciesManager import PythonDependencyChecker
        return PythonDependencyChecker.areDependenciesSatisfied()
    
    @staticmethod
    def downloadDependenciesAndRestart():
        from Scripts.PythonDependenciesManager import PythonDependencyChecker
        progressDialog = slicer.util.createProgressDialog(maximum=0)
        PythonDependencyChecker.installDependenciesIfNeeded(progressDialog)
        progressDialog.close()
        slicer.app.restart()

            


#
# SlicerGPTLogic
#

import requests
import sys
from Scripts.Utils import extract_mrml_scene_as_text
from Scripts.Utils import markdown_to_html
import json

class SlicerGPTLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """
        Starts the local server and connect alm the callbacks.
        """
        ScriptedLoadableModuleLogic.__init__(self)
        self.dialogue = []
        self.streamingBuffer = ""
        self.stderr_buffer = ""
        # self.chunkTimer = qt.QTimer()
        # self.chunkTimer.setInterval(10)  # 100 ms
        # self.chunkTimer.timeout.connect(self.read_next_chunk)
        self.proc = qt.QProcess()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if base_dir not in sys.path:
            sys.path.append(base_dir)
        server_path = os.path.join(base_dir, "SlicerGPT", "Scripts", "LocalServer.py")
        self.proc.setProgram("PythonSlicer")
        self.proc.setArguments([server_path])

        self.proc.readyReadStandardOutput.connect(self.handle_stdout)
        self.proc.readyReadStandardError.connect(self.handle_stderr)
        self.start()
        self.proc.started.connect(lambda: print("[INFO] Server started"))
        self.proc.finished.connect(lambda: print("[INFO] Server stopped"))

        from Scripts.AsyncRequest import AsyncRequest
        self.async_request = AsyncRequest()
        self.async_request.requestFinished.connect(self.handleResponse)
        self.async_request.requestFailed.connect(self.handleError)
        self.async_request.requestChunk.connect(self.handleChunk)

        self.widget = None
        self.serverReady = False

        self.think = False
        self.useApi = False
        self.useOllama = False

    def handleChunk(self, chunk):
        self.streamingBuffer += chunk
        # print(self.streamingBuffer)
        if self.widget:
            self.widget.updateConversationLive(self.streamingBuffer)

    # def read_next_chunk(self):
    #     try:
    #         chunk = self.model.read_chunk()
    #         if chunk == "[[DONE]]":
    #             self.chunkTimer.stop()
    #             self.dialogue.pop()  # remove "Generating response..."
    #             self.dialogue.append({"role": "assistant", "content": self.streamingBuffer})
    #             if self.widget:
    #                 self.widget.updateConversation(self.formatDialogue())
    #         else:
    #             self.streamingBuffer += chunk
    #             if self.widget:
    #                 self.widget.updateConversationLive(self.streamingBuffer)
    #     except Exception as e:
    #         print(f"[ERROR] Reading chunk: {e}")


        
    def getParameterNode(self):
        return SlicerGPTParameterNode(super().getParameterNode())
    
    def start(self):
        print("[INFO] Starting process...")
        self.proc.start()

    def checkServerInitialised(self, output):
        if "Uvicorn running on http://127.0.0.1:8081" in output:
            print("[INFO] Server ready")
            self.serverReady = True
            if self.widget:
                self.widget.onServerReady()

    def handle_stdout(self):
        output = self.proc.readAllStandardOutput().data().decode()
        print("[STDOUT]", output)
        if not self.serverReady:
            self.checkServerInitialised(output)
        

    def handle_stderr(self):
        raw = self.proc.readAllStandardError().data()
        error = raw.decode(errors="replace")
        if "[[CHUNK]]" in error:
            if "[[DONE]]" in error:
                self.handleResponse({"content": self.streamingBuffer.strip()})
                return
            chunk = error.split("[[CHUNK]]")[-1]
            self.handleChunk(chunk[:-1].strip("\r"))
        print("[STDERR]", error)
        if not self.serverReady:
            self.checkServerInitialised(error)

    def handleResponse(self, response_data):
        """
        Handle the received response during the async request
        """
        print(response_data)

        self.dialogue.pop()
        self.dialogue.append({"role": "assistant", "content": response_data['content']})

        if self.widget:
            self.widget.updateConversation(self.formatDialogue())
            
    def handleError(self, error_message):
        """
        Handle errors during the async request.
        """

        self.dialogue.append({"role": "assistant", "content": f"Server communication error: {error_message}"})
        
        if self.widget:
            self.widget.updateConversation(self.formatDialogue())
    
    def setThinking(self, think):
        """
        Change the base chatbot thinking mode.
        """
        self.think = think

    def setApi(self, useApi):
        self.useApi = useApi
    
    def setOllama(self, useOllama):
        self.useOllama = useOllama

    def checkStatus(self, data):
        if data.get("status") == "ok":
            return True
        return False
    
    def addApiKey(self, key):
        apiKey = {"key": key}
        requests.post("http://127.0.0.1:8081/addKey", json=apiKey)
    
    def formatDialogue(self) -> str:
        """
        Return the formatted text of the dialogue, it will be displayed in the conversation widget.
        """
        finalDialogue = []
        for message in self.dialogue:
            content = markdown_to_html(message["content"])
            if message["role"] == "assistant":
                finalDialogue.append(f'<div style="text-align:left; margin: 5px;"><span style="color:red; font-weight:bold;">SlicerGPT:</span><br>{content}</div>')
            elif message["role"] == "user":
                finalDialogue.append(f'<div style="text-align:right; margin: 5px;"><span style="color:blue; font-weight:bold;">You:</span><br>{content}</div>')


        return "\n\n".join(finalDialogue)


    def process(self, message) -> str:
        """
        Run the processing algorithm, send the question to the model.
        """

        logging.info("Processing started")

        self.dialogue.append(message)
        temp_message = {"role": "assistant", "content": "Generating response..."}
        self.dialogue.append(temp_message)
        
        message["mrml_scene"] = extract_mrml_scene_as_text()
        message["think"] = self.think
        message["use_api"] = self.useApi
        
        formatted_dialogue = self.formatDialogue()
        self.streamingBuffer = ""
        if self.useOllama:
            self.async_request.stream("http://127.0.0.1:8081/generateStream", message)
        else:
            self.async_request.post("http://127.0.0.1:8081/generate", message)
        
        return formatted_dialogue
    
    def performTest(self):
        
        try:
            response = requests.get("http://127.0.0.1:8081/health")
            
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "ok":
                print(f"Test passed : status = {data.get('status')}")
                return {"passed": True, "status": data.get("status")}
            else:
                print(f"Test failed : status = {data.get('status')}")
                return {"passed": False, "status": data.get("status")}
                
        except requests.exceptions.RequestException as e:
            print(f"Request error : {e}")
            return {"passed": False, "status": e}
        except json.JSONDecodeError as e:
            print(f"Parsing JSON error : {e}")
            return {"passed": False, "status": e}
        except Exception as e:
            print(f"Unexpected error : {e}")
            return {"passed": False, "status": e}



#
# SlicerGPTTest
#
import time


class SlicerGPTTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_SlicerGPT1()

    def test_SlicerGPT1(self):
        """Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """
        
        self.delayDisplay("Starting the test")

        # Test the module logic

        logic = SlicerGPTLogic()
        time.sleep(30.0)
        response = logic.performTest()

        if response.get("passed") is True:
            self.delayDisplay("Test passed")
            requests.get("http://127.0.0.1:8081/shutdown")
        else:
            self.delayDisplay(f"Test failed, received {response.get('status')}")
