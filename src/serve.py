from Authenticator import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=9000, log_level="info",log_config="logging.yaml")  # ◄── 核心就是这个参数！)
