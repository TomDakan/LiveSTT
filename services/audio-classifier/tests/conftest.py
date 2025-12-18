import sys
from unittest.mock import MagicMock

# Mock NATS and OpenVINO if missing
class MockNats:
    pass

class MockJsApi:
    RetentionPolicy = MagicMock()
    StorageType = MagicMock()

# Helper to mock a package structure
def mock_module(name):
    m = MagicMock()
    m.__path__ = [] # Mark as package
    sys.modules[name] = m
    return m

if "nats" not in sys.modules:
    nats = mock_module("nats")

if "nats.aio" not in sys.modules:
    mock_module("nats.aio")

if "nats.aio.client" not in sys.modules:
    mock_module("nats.aio.client")

if "nats.js" not in sys.modules:
    mock_module("nats.js")

if "nats.js.api" not in sys.modules:
    m = mock_module("nats.js.api")
    m.RetentionPolicy = MagicMock()
    m.StorageType = MagicMock()

if "openvino" not in sys.modules:
    mock_module("openvino")

if "openvino.runtime" not in sys.modules:
    mock_module("openvino.runtime")
