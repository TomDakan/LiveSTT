import sys

import zmq


def main():
    context = zmq.Context()

    # XSUB: Receives messages from Publishers (Producers)
    # "Frontend" of the proxy
    frontend = context.socket(zmq.XSUB)
    frontend.bind("tcp://0.0.0.0:5555")

    # XPUB: Sends messages to Subscribers (Consumers)
    # "Backend" of the proxy
    backend = context.socket(zmq.XPUB)
    backend.bind("tcp://0.0.0.0:5556")

    print("Audio Broker initialized.")
    print(" - Input (XSUB): tcp://*:5555")
    print(" - Output (XPUB): tcp://*:5556")
    sys.stdout.flush()

    # Start the proxy
    # This blocks indefinitely and shuffles packets between sockets
    try:
        zmq.proxy(frontend, backend)
    except KeyboardInterrupt:
        print("Broker stopping...")
    finally:
        frontend.close()
        backend.close()
        context.term()


if __name__ == "__main__":
    main()
