from llama_cpp import Llama
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

from queue import Queue
import asyncio
from threading import Thread

import os
os.environ["INFERENCE_API_TOKEN"] = ""


FAISS_DIR = "./SlicerFAISS"

class Model:
    def __init__(self, manager):

        self.llm = Llama.from_pretrained(
            repo_id="unsloth/Qwen3-0.6B-GGUF",
	        filename="Qwen3-0.6B-Q8_0.gguf",
            verbose=True,
            n_ctx=8196,
            n_gpu_layers=-1,
            n_threads=1
        )
        self.endpoint = "https://models.github.ai/inference"
        self.api_model = "openai/gpt-4.1"
        self.client = None

        self.ollama_model = "qwen3:0.6b"
        self.queue = Queue()

        self.manager = manager
        self.history = [{
            "role": "system",
            "content": (
                "You are an expert 3D Slicer technical assistant. Your responses must be:\n"
                "1. TECHNICALLY PRECISE - Use exact module/feature names and correct steps\n"
                "2. CONCISE - Break complex tasks into numbered steps\n"
                "3. PRACTICAL - Include troubleshooting tips for common issues\n"
                "4. SAFE - Never suggest modifying critical system files\n\n"
                
                "Response Format Guidelines:\n"
                "- Start with a brief direct answer\n"
                "- Follow with detailed steps if needed\n"
                "- For GUI operations, specify the exact menu path (e.g. 'Modules > Segment Editor')\n"
                
                "Documentation Resources:\n"
                "- Official Manual: https://slicer.readthedocs.io\n"
                "- User Forum: https://discourse.slicer.org/\n"
                "- Training: https://training.slicer.org/\n\n"
                
                "Special Cases:\n"
                "- For Python scripting questions, include both the script and where to paste it\n"
                "- For DICOM issues, verify if the user has the DICOM module loaded\n"
                "- When unsure, you have exact Slicer version in the MRML scene the user will give to you"
            )
        }]

        # self.history = []
        self.has_history = True

    def initialize_azure_client(self, key):
        safe_key = "".join(key.split())
        self.client = ChatCompletionsClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(safe_key),
        )

    def think(self, enable_thinking):
        return " /think" if enable_thinking is True else " /no_think"


    def generate_response(self, user_input, mrml_scene, enable_thinking, use_api):
        
        # print(mrml_scene)

        docs = self.manager.search(user_input, k=3)
        print(docs[0])
        context = (
            "Context documents:\n"
            + "\n---\n".join([doc.page_content for doc in docs]) + "\n\n"

            "MRML Scene:\n"
            + mrml_scene + "\n\n"

            "Now, based on this context, the recent conversation, and your internal knowledge of 3D Slicer, "
            "answer the user's question as a real 3D Slicer expert would. "
            "Be technically accurate, easy to understand, and do not make up facts.\n\n"

            f"User question: {user_input}"
        )
        
        think = self.think(enable_thinking) if not use_api else ""
        messages = self.history + [{"role": "user", "content": context + user_input + think}]

        if use_api and self.client is not None:
            try:
                resp = self.client.complete(
                messages=messages,
                temperature=0,
                top_p=1.0,
                model=self.api_model
                )
            except Exception as e:
                print(f"An error occured while calling the client: {e}, using the Base model instead...")
                messages[-1]["content"] += self.think(enable_thinking)
                resp = self.llm.create_chat_completion(
                messages=messages,
                )
                
    
        else:
            resp = self.llm.create_chat_completion(
                messages=messages,
            )

        response = resp["choices"][0]["message"]["content"]

        # Update history
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": response})

        return response

    async def _stream_response(self, user_input, mrml_scene, enable_thinking):
        from ollama import AsyncClient
        import ollama
        # ollama.pull(self.model_name)
        client = AsyncClient()
        docs = self.manager.search(user_input, k=3)
        think = self.think(enable_thinking) if "qwen3" in self.ollama_model.lower() else ""
        context = (
            "Context documents:\n"
            + "\n---\n".join([doc.page_content for doc in docs]) + "\n\n"

            "MRML Scene:\n"
            + mrml_scene + "\n\n"

            "Now, based on this context, the recent conversation, and your internal knowledge of 3D Slicer, "
            "answer the user's question as a real 3D Slicer expert would. "
            "Be technically accurate, easy to understand, and do not make up facts.\n\n"

            f"User question: {user_input}"
        )

        messages = self.history + [{"role": "user", "content": context + think}]
        self.history.append({"role": "user", "content": user_input})
        response = ""
        if enable_thinking:
            sampling_options = {
                "temperature": 0.6,
                "top_p": 0.95,
                "top_k": 20,
                "min_p": 0.0,
            }
        else:
            sampling_options = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "min_p": 0.0,
            }
        async for chunk in await client.chat(
            model=self.ollama_model,
            messages=messages,
            stream=True,
            options=sampling_options
        ):
            content = chunk["message"]["content"]
            self.queue.put(content)
            response = response + content
        self.history.append({"role": "user", "content": response})
        self.queue.put("[[DONE]]")

    def start_streaming(self, user_input, mrml_scene, think_flag):
        def run():
            asyncio.run(self._stream_response(user_input, mrml_scene, think_flag))
        Thread(target=run, daemon=True).start()

    def read_chunk(self):
        return self.queue.get()

# if __name__ == "__main__":

    # manager = VectorStoreManager(FAISS_DIR)
    # chatbot = Model(manager=manager)
    # prompts = [
    #     'What is 3D Slicer?',
    #     'How to create a custom extension for 3D Slicer using Python?',
    #     'How to extract a volume using the Segment Editor module?',
    #     'What is the difference between vtkMRMLModelNode and vtkMRMLSegmentationNode?',
    #     'How to export a segmentation as an STL file using Python?',
    #     'How to load a large DICOM volume without slowing down Slicer?',
    #     'How to use the CLI module to automate a task in C++?',
    #     'What is the structure of a .mrml file in 3D Slicer?',
    #     'How to enable GPU acceleration for volume rendering?',
    #     'How to save a Python script as a module in Slicer?',
    #     'Can 3D Slicer run in headless mode (without GUI)?',
    #     'How to interface 3D Slicer with a DICOM PACS server?',
    #     'How to apply a smoothing filter to a 3D model in Slicer?',
    #     'How to automatically save modifications to a node?',
    #     'What is the best method to merge multiple segmentations?',
    #     'How to use the Elastix registration tool in Slicer?',
    # ]
    # import time
    
    # for pr in prompts:
    #     start = time.perf_counter()
    #     response = chatbot.generate_response(pr)
    #     end = time.perf_counter()
    #     print(pr)
    #     print(response)
    #     print(f"Generate in {end - start:.4f} seconds.")
    #     print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")