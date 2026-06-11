from ollama import chat

import os
os.environ["INFERENCE_API_TOKEN"] = ""


FAISS_DIR = "./SlicerFAISS"

class Model:
    def __init__(self, manager):

        self.ollama_model = "minimax-m3:cloud"

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
                "- Do not call the user by it's name\n"
                
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

        self.history = []
        self.has_history = True

    def stream_response(self, user_input, mrml_scene, enable_thinking):
        docs = self.manager.search(user_input, k=3)
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

        messages = self.history + [{"role": "user", "content": context}]
        self.history.append({"role": "user", "content": user_input})
        response = ""
        first = True
        last = False

        sampling_options = {
            "temperature": 0.6 if enable_thinking else 0.7,
            "top_p": 0.95 if enable_thinking else 0.8,
            "top_k": 20,
            "min_p": 0.0,
        }

        for chunk in chat(
            model=self.ollama_model,
            messages=messages,
            stream=True,
            options=sampling_options
        ):
            if first:
                if enable_thinking:
                    content = "<think> " + chunk.message.thinking if chunk.message.thinking is not None else ""
                else:
                    content = "<think> </think>\n\n" + '' if chunk.message.thinking is not None else chunk.message.content
                    last = True
                first = False
            elif last is False and chunk.message.content != '':
                content = "</think>\n\n" + chunk.message.content
                last = True
            else:
                content = chunk.message.thinking if chunk.message.thinking is not None and last is False else chunk.message.content
            response += content
            yield content


        self.history.append({"role": "assistant", "content": response})

    def pull_model_if_needed(self, model_name):
        self.ollama_model = model_name
        try:
            print(f"Trying to pull missing model: {self.ollama_model}")
            ollama.pull(self.ollama_model)
            print(f"Model {self.ollama_model} pulled successfully.")
        except Exception as e:
            print(f"Failed to pull model {self.ollama_model}: {e}")

# if __name__ == "__main__":

#     from VectorStoreManager import VectorStoreManager
#     manager = VectorStoreManager(FAISS_DIR)
#     chatbot = Model(manager=manager)
#     prompts = [
#         'What is 3D Slicer?',
#         'How to create a custom extension for 3D Slicer using Python?',
#         'How to extract a volume using the Segment Editor module?',
#         'What is the difference between vtkMRMLModelNode and vtkMRMLSegmentationNode?',
#         'How to export a segmentation as an STL file using Python?',
#         'How to load a large DICOM volume without slowing down Slicer?',
#         'How to use the CLI module to automate a task in C++?',
#         'What is the structure of a .mrml file in 3D Slicer?',
#         'How to enable GPU acceleration for volume rendering?',
#         'How to save a Python script as a module in Slicer?',
#         'Can 3D Slicer run in headless mode (without GUI)?',
#         'How to interface 3D Slicer with a DICOM PACS server?',
#         'How to apply a smoothing filter to a 3D model in Slicer?',
#         'How to automatically save modifications to a node?',
#         'What is the best method to merge multiple segmentations?',
#         'How to use the Elastix registration tool in Slicer?',
#     ]
#     import time
    
#     for pr in prompts:
#         print(pr)
#         start = time.perf_counter()
#         for chunk in chatbot.stream_response(pr, "", False):
#             print(chunk, end="", flush=True)
#         end = time.perf_counter()
#         print(f"Generate in {end - start:.4f} seconds.")
#         print("%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%")