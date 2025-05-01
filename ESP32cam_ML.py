import cv2
import numpy as np
import urllib.request
import requests  
import socket

whT = 320
confThreshold = 0.6  
nmsThreshold = 0.4  

# Load YOLO model & class names
classNames = open('coco.names').read().strip().split("\n")
net = cv2.dnn.readNetFromDarknet("yolov3.cfg", "yolov3.weights")
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

FRAME_WIDTH = 800  
MIDDLE_X = FRAME_WIDTH // 2  

def get_local_subnet():
    """ Automatically get the local subnet based on the current network. """
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)  # Get local machine IP
    subnet = ".".join(local_ip.split(".")[:3])  # Extract subnet (e.g., 192.168.116)
    return subnet

def find_esp32():
    """ Scan local network to find ESP32 dynamically. """
    subnet = get_local_subnet()
    print(f"\U0001F50D Scanning subnet: {subnet}.XXX")
    
    for i in range(126, 255):  # Scan 192.168.xxx.100 - 192.168.xxx.200
        ip = f"{subnet}.{i}"
        try:
            response = requests.get(f"http://{ip}/get_ip", timeout=1)
            data = response.json()
            if "ip" in data:
                print(f"✅ ESP32 Found at {data['ip']}")
                return data["ip"]
        except (requests.exceptions.RequestException, ValueError):
            continue
    return None  # If ESP32 isn't found

ESP32_IP = find_esp32()
if not ESP32_IP:
    print("❌ Could not find ESP32. Exiting.")
    exit()

ESP32_URL = f"http://{ESP32_IP}/update_zones"
CAMERA_URL = f"http://{ESP32_IP}/cam-hi.jpg"

print(f"✅ Using ESP32 IP: {ESP32_IP}")

def adjust_brightness(image, gamma=1.5):
    invGamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** invGamma * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(image, table)

def detect_zones(outputs, img):
    img = adjust_brightness(img)
    hT, wT, _ = img.shape
    bbox, classIds, confs = [], [], []
    found_zone1, found_zone2 = False, False

    for output in outputs:
        for det in output:
            scores = det[5:]
            classId = np.argmax(scores)
            confidence = scores[classId]
            if confidence > confThreshold and classNames[classId] == "person":
                w, h = int(det[2] * wT), int(det[3] * hT)
                x, y = int((det[0] * wT) - w / 2), int((det[1] * hT) - h / 2)
                left_edge, right_edge = x, x + w
                
                if left_edge < MIDDLE_X and right_edge > MIDDLE_X:
                    found_zone1, found_zone2 = True, True
                elif right_edge <= MIDDLE_X:
                    found_zone1 = True  
                else:
                    found_zone2 = True  
                
                bbox.append([x, y, w, h])
                classIds.append(classId)
                confs.append(float(confidence))

    indices = cv2.dnn.NMSBoxes(bbox, confs, confThreshold, nmsThreshold)
    if len(indices) > 0:
        for i in indices.flatten():
            x, y, w, h = bbox[i]
            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 255), 2)
            cv2.putText(img, "PERSON", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    
    cv2.line(img, (MIDDLE_X, 0), (MIDDLE_X, hT), (0, 255, 0), 2)
    if found_zone1:
        cv2.putText(img, "Zone 1 Active", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if found_zone2:
        cv2.putText(img, "Zone 2 Active", (FRAME_WIDTH - 200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    relay_data = {"zone1": int(found_zone1), "zone2": int(found_zone2)}
    try:
        requests.post(ESP32_URL, data=relay_data)
        print(f"Sent to ESP32: {relay_data}")
    except Exception as e:
        print("Failed to send data to ESP32:", e)
    
    return img

while True:
    try:
        img_resp = urllib.request.urlopen(CAMERA_URL, timeout=2)
        imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)
        img = cv2.imdecode(imgnp, -1)

        if img is None:
            print("⚠️ Failed to capture image. Retrying...")
            continue

        blob = cv2.dnn.blobFromImage(img, 1 / 255, (whT, whT), [0, 0, 0], 1, crop=False)
        net.setInput(blob)
        layernames = net.getLayerNames()
        outputNames = [layernames[i - 1] for i in net.getUnconnectedOutLayers().flatten()]
        outputs = net.forward(outputNames)
        
        img = detect_zones(outputs, img)
        cv2.imshow('Live Stream', img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    except Exception as e:
        print("❌ Error processing frame:", e)

cv2.destroyAllWindows()
