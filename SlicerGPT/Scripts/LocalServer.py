import os
import signal
import time
import logging
import sys
import threading
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import StreamingResponse
import uvicorn
from pydantic import BaseModel
from typing import Any, Optional
from Model import Model
from VectorStoreManager import VectorStoreManager
import json

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

class Message(BaseModel):
    role: str
    content: str
    mrml_scene: Optional[str] = None
    think: bool

class ThinkBool(BaseModel):
    think: bool

class ModelName(BaseModel):
    model_name: str


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

@inferenceServer.post("/pullModel")
async def setModelName(model_name: ModelName):
    chatbot.pull_model_if_needed(model_name.model_name)
    logger.info(model_name.model_name + " pulled !")
    
@inferenceServer.post("/generateStream")
async def generate(message: Message):

    async def event_stream():
        for chunk in chatbot.stream_response(
            message.content,
            message.mrml_scene,
            message.think
        ):
            yield f"data: {json.dumps({'token': chunk})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


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
    uvicorn.run(
        "LocalServer:inferenceServer",
        host="127.0.0.1",
        port=8081,
        log_level="info",
        loop="asyncio",
        http="httptools",
        ws="websockets",
        reload=False,
        access_log=False,
        workers=1,
    )


if __name__=="__main__":
    def handle_sigterm(signum, frame):
        logger.info("SIGTERM received, shutting down")
        global server_should_exit
        server_should_exit = True
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    run_server()