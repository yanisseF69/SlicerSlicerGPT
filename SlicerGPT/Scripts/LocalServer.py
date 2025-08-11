import os
import signal
import time
import logging
import sys
import threading
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn
from pydantic import BaseModel
from typing import Any, Optional
from Model import Model
from VectorStoreManager import VectorStoreManager

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

class Message(BaseModel):
    role: str
    content: str
    mrml_scene: Optional[str] = None
    think: bool
    use_api: bool

class ThinkBool(BaseModel):
    think: bool

class ApiKey(BaseModel):
    key: str


inferenceServer = FastAPI()

server_should_exit = False
server_pid = os.getpid()


logger.info("Initializing vector store and model...")
start_time = time.time()
base_dir = os.path.dirname(os.path.abspath(__file__))
faiss_path = os.path.join(base_dir, "..", "Data", "SlicerFAISS")

manager = VectorStoreManager(faiss_path)
chatbot = Model(manager=manager)
logger.info(f"Initialization complete in {time.time() - start_time:.2f} seconds")

@inferenceServer.post("/setThink")
async def setThink(think: ThinkBool):
    chatbot.enable_thinking = think.think


@inferenceServer.post("/generate")
async def generate(message: Message):
    logger.info("Starting generate function execution")
    start_time = time.time()
    
    try:
        response = chatbot.generate_response(message.content, message.mrml_scene, message.think, message.use_api)
        logger.info(f"generate function completed in {time.time() - start_time:.4f} seconds")
        return response
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        raise

@inferenceServer.post("/generateStream")
async def generate(message: Message):
    chatbot.start_streaming(message.content, message.mrml_scene, message.think)

    async def event_stream():
        while True:
            chunk = chatbot.read_chunk()
            logger.info("[[CHUNK]]" + chunk)
            if chunk == "[[DONE]]":
                break
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@inferenceServer.post("/addKey")
async def addKey(apiKey: ApiKey):
    logger.info("Adding API key")
    try:
        chatbot.initialize_azure_client(apiKey.key)
        logger.info("API Key added.")
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")



@inferenceServer.get("/health")
async def health_check():
    """Simple enpoint to check the server's status"""
    return {"status": "ok", "timestamp": time.time()}


@inferenceServer.get("/shutdown")
async def shutdown():
    """Endpoint who stops the server"""
    logger.info("Shutdown request received")
    
    def stop_server():
        logger.info("Shutting down server...")
        time.sleep(0.5)
        global server_should_exit
        server_should_exit = True
        
        os.kill(server_pid, signal.SIGTERM)
    
    threading.Thread(target=stop_server).start()
    return {"status": "shutting_down"}


def run_server():
    logger.info(f"Starting server on port 8081, PID: {server_pid}")
    
    config = uvicorn.Config(
        app=inferenceServer, 
        host="127.0.0.1",
        port=8081,
        log_level="info",
        loop="asyncio",
        workers=1
    )
    
    server = uvicorn.Server(config)
    server.run()


if __name__=="__main__":
    def handle_sigterm(signum, frame):
        logger.info("SIGTERM received, shutting down")
        global server_should_exit
        server_should_exit = True
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    run_server()