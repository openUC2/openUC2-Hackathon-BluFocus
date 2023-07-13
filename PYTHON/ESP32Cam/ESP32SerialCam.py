#%%
import serial
import time
import serial.tools.list_ports
from PIL import Image
import base64
import io
import numpy as np
import matplotlib.pyplot as plt
import tifffile as tif

import cv2

def connect_to_usb_device(manufacturer="Espressif"):
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if port.manufacturer == manufacturer or port.manufacturer == "Microsoft":
            try:
                ser = serial.Serial(port.device, baudrate=2000000, timeout=1)
                print(f"Connected to device: {port.description}")
                ser.write_timeout = 1
                return ser
            except serial.SerialException:
                print(f"Failed to connect to device: {port.description}")
    print("No matching USB device found.")
    return None

# Specify the manufacturer to connect to
manufacturer = 'Espressif'

# Connect to the USB device
serialdevice = connect_to_usb_device(manufacturer)


#%%
iError = 0

t0 = time.time()
message = ""
imageString = ""

#cv2.startWindowThread()

serialdevice.write(('t10\n').encode())
serialdevice.readline()

while True:
  try:
      #read image and decode
      #serialdevice.write(b"")
      serialdevice.write(('\n').encode())
      # don't read to early
      time.sleep(.05)
      
      # Read a frame from the serial port
      frame_size = 320 * 240
      frame_bytes = serialdevice.read(frame_size)

      # Convert the bytes to a numpy array
      frame = np.frombuffer(frame_bytes, dtype=np.uint8)
      frame = frame.reshape((320, 240))

      #imageB64 = str(imageB64).split("+++++")[-1].split("----")[0]
      print("framerate: "+(str(1/(time.time()-t0))))
      t0 = time.time()
      if cv2.waitKey(25) & 0xFF == ord('q'):
          break
      cv2.imshow("image", frame)
      
      serialdevice.flushInput()
      serialdevice.flushOutput()
      serialdevice.readline()

      frame = np.mean(frame,-1)
      #cv2.waitKey(-1)
      #plt.imshow(image), plt.show()
      #serialdevice.flushInput()
      #serialdevice.flushOutput()
      #tif.imsave("test_stack_esp32.tif", image, append=True)
  except Exception as e:
      print("Error")
      print(e)
      serialdevice.flushInput()
      serialdevice.flushOutput()
      iError += 1
      #serialdevice.reset_input_buffer()
      # reset device here 
      if iError % 20:
            try:
                # close the device - similar to hard reset
                serialdevice.setDTR(False)
                serialdevice.setRTS(True)
                time.sleep(.1)
                serialdevice.setDTR(False)
                serialdevice.setRTS(False)
                time.sleep(.5)
                #serialdevice.close()
            except Exception as e: pass
            serialdevice = connect_to_usb_device()
            nTrial = 0
      
    
print(iError)

#%%
        
        
''' ESP CODE
#include "esp_camera.h"
#include <base64.h>

#define BAUD_RATE 2000000

#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 10
#define SIOD_GPIO_NUM 40
#define SIOC_GPIO_NUM 39

#define Y9_GPIO_NUM 48
#define Y8_GPIO_NUM 11
#define Y7_GPIO_NUM 12
#define Y6_GPIO_NUM 14
#define Y5_GPIO_NUM 16
#define Y4_GPIO_NUM 18
#define Y3_GPIO_NUM 17
#define Y2_GPIO_NUM 15
#define VSYNC_GPIO_NUM 38
#define HREF_GPIO_NUM 47
#define PCLK_GPIO_NUM 13

#define LED_GPIO_NUM 21

void grabImage();
void cameraInit();


void setup()
{
  Serial.begin(BAUD_RATE);

  cameraInit();
}

bool isCROP = false;
int Nx = 320;
int Ny = 240;
int Nroi = 50;
int x = 320 / 2;
int y = 240 / 2;
bool isStreaming = true;

void crop_image(camera_fb_t *fb, unsigned short cropLeft, unsigned short cropRight, unsigned short cropTop, unsigned short cropBottom)
{
  unsigned int maxTopIndex = cropTop * fb->width * 2;
  unsigned int minBottomIndex = ((fb->width * fb->height) - (cropBottom * fb->width)) * 2;
  unsigned short maxX = fb->width - cropRight; // In pixels
  unsigned short newWidth = fb->width - cropLeft - cropRight;
  unsigned short newHeight = fb->height - cropTop - cropBottom;
  size_t newJpgSize = newWidth * newHeight * 2;

  unsigned int writeIndex = 0;
  // Loop over all bytes
  for (int i = 0; i < fb->len; i += 2)
  {
    // Calculate current X, Y pixel position
    int x = (i / 2) % fb->width;

    // Crop from the top
    if (i < maxTopIndex)
    {
      continue;
    }

    // Crop from the bottom
    if (i > minBottomIndex)
    {
      continue;
    }

    // Crop from the left
    if (x <= cropLeft)
    {
      continue;
    }

    // Crop from the right
    if (x > maxX)
    {
      continue;
    }

    // If we get here, keep the pixels
    fb->buf[writeIndex++] = fb->buf[i];
    fb->buf[writeIndex++] = fb->buf[i + 1];
  }

  // Set the new dimensions of the framebuffer for further use.
  fb->width = newWidth;
  fb->height = newHeight;
  fb->len = newJpgSize;
}

void loop()
{
  // Check for incoming serial commands
  if (Serial.available() > 0)
  {
    delay(50);
    Serial.read(); // Read the incoming command until a newline character is encountered
    grabImage();

    }
  
}

void cameraInit()
{

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  // config.frame_size = FRAMESIZE_QVGA;
  // config.pixel_format = PIXFORMAT_JPEG; // for streaming
  // config.pixel_format = PIXFORMAT_RGB565; // for face detection/recognition
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  if (isCROP)
  {
    config.pixel_format = PIXFORMAT_RGB565;
    config.frame_size = FRAMESIZE_SXGA;
    config.fb_count = 2;
  }
  else
  {
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA; // for streaming}

    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK)
  {
    return;
  }

  sensor_t *s = esp_camera_sensor_get();
  s->set_hmirror(s, 1);
  s->set_vflip(s, 1);
}
void grabImage()
{

  camera_fb_t *fb = esp_camera_fb_get();
  if (isCROP)
  {

    // Crop image (frame buffer, cropLeft, cropRight, cropTop, cropBottom)
    unsigned short cropLeft = x - Nroi / 2;
    unsigned short cropRight = x + Nroi / 2;
    unsigned short cropTop = y - Nroi / 2;
    unsigned short cropBottom = y + Nroi / 2;

    crop_image(fb, 550, 450, 100, 190);
    // crop_image(fb, cropLeft, cropRight, cropTop, cropBottom);
    //  Create a buffer for the JPG in psram
    uint8_t *jpg_buf = (uint8_t *)heap_caps_malloc(200000, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);

    if (jpg_buf == NULL)
    {
      printf("Malloc failed to allocate buffer for JPG.\n");
    }
    else
    {
      size_t jpg_size = 0;

      // Convert the RAW image into JPG
      // The parameter "31" is the JPG quality. Higher is better.
      fmt2jpg(fb->buf, fb->len, fb->width, fb->height, fb->format, 31, &jpg_buf, &jpg_size);
      printf("Converted JPG size: %d bytes \n", jpg_size);
      String encoded = base64::encode(jpg_buf, jpg_size);
      Serial.write(encoded.c_str(), encoded.length());
      Serial.println();
    }
  }
  else
  {

    if (!fb || fb->format != PIXFORMAT_JPEG)
    {
      Serial.println("Failed to capture image");
    }
    else
    {
      delay(40);

      String encoded = base64::encode(fb->buf, fb->len);
      Serial.write(encoded.c_str(), encoded.length());
      Serial.println();
    }

    esp_camera_fb_return(fb);
  }
}
'''
# %%
