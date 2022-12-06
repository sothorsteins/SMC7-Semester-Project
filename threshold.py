import socket
from datetime import datetime

import numpy as np

from pythonosc import dispatcher
from pythonosc import osc_server
from pythonosc import udp_client


class OSC:
  # Networking variables
  listen_ip   = "0.0.0.0"
  listen_port = 1235
  send_ip     = "127.0.0.1"
  send_port   = 9877

  # Threshold variables
  low_bool = False
  target = 90
  low_thres_offset = 45
  low_thresh = target - low_thres_offset

  # Velocity variables
  current_vel   = 0
  current_angle = None
  current_time  = None
  prev_angle    = None
  prev_time     = None
  vel_MA_length = 60 # determines how fast velocity changes
  vel_MA_vector = np.zeros((1, vel_MA_length))
  vel_MA_result = 0
  vel_max       = 50
  vel_min       = 45

  # udp sender
  sender = udp_client.SimpleUDPClient(send_ip, send_port)
  sender.send_message("/test", "helloworld")


  DEBUG = True
  VERBOSE = False
  """
  if self.DEBUG is set to True, print debug msgs
  """
  def debug_print(self, msg):
    if self.DEBUG:
      print(msg)

  """
  if self.VERBOSE is set to True, print verbose msgs
  """
  def verbose_print(self, msg):
    if self.VERBOSE:
      print(msg)


  """
  Calculate and send moving average of angular velocity
  NOTE: angle = shoulder / wrist
  """
  def calculate_vel_MA(self):
    self.current_time  = datetime.now()
    if not self.prev_angle is None:
      # Current velocity
      delta_time    = (self.current_time - self.prev_time).total_seconds()
      delta_angle   = abs(self.prev_angle - self.current_angle)
      self.current_vel = delta_angle / delta_time
      if self.current_vel < self.vel_min:
        self.current_vel = 0

      # Calculate moving average
      self.vel_MA_vector = np.roll(self.vel_MA_vector, 1)
      self.vel_MA_vector[0, 0] = self.current_vel
      self.vel_MA_result = np.sum(self.vel_MA_vector) / self.vel_MA_length


      # Normalize result
      self.vel_MA_result /= self.vel_max
      if self.vel_MA_result > 1:
        self.vel_MA_result = 1

      # Send normalized result to Max
      self.sender.send_message("/velocity", self.vel_MA_result)

    # Save angle and time for next calculation
    self.prev_angle    = self.current_angle
    self.prev_time     = self.current_time

    self.verbose_print(f"MA of velocity: {self.vel_MA_result} (normalized and capped)")


  """
  Update angle when new data changes recieved from Max
  NOTE: angle = shoulder / wrist
  """
  def set_angle(self, address, angle):
    # Set angle
    self.current_angle = angle
    self.verbose_print(f"current angle: {angle}")

    # Calculate velocity moving average
    self.calculate_vel_MA()

    # Set low_thresh to True if new angle is below threshold
    if (self.current_angle <= self.low_thresh) and not self.low_bool:
      self.low_bool = True
      self.debug_print(f"low threshold passed")

    # Check if angle is higher then target
    if (self.current_angle >= self.target) and self.low_bool:
      self.low_bool = False
      self.sender.send_message("/trigger", 1)

      self.debug_print("Gratification trigger sent")


  """
  Update target angle when changed in Max
  """
  def set_target(self, address, target):
    self.target = target
    self.low_thresh = target - self.low_thres_offset
    self.debug_print(f"target angle changed: {target}")


  """
  Set up server
  """
  def listen(self, ip, port):
    # dispatcher to receive message
    disp = dispatcher.Dispatcher()
    disp.map("/angle", self.set_angle)
    disp.map("/target", self.set_target)
    disp.map("/test", print)

    # server to listen
    server = osc_server.ThreadingOSCUDPServer((ip, port), disp)
    print(f"Serving on {format(server.server_address)}")
    server.serve_forever()


  """
  Constructor
  """
  def __init__(self, listen_ip = "0.0.0.0", listen_port = 1235, send_ip = "localhost", send_port = 9877):
    self.listen_ip   = listen_ip
    self.listen_port = listen_port
    self.send_ip     = send_ip
    self.send_port   = send_port

    self.listen(listen_ip, listen_port)

    self.sender.send_message("hello", 1234)


"""
Port numbers default to the same as the numbers we have in Max.
That being: 9877 for sending out triggers, and 1235 for recieving data in python.
Vice versa for Max, so recieve on 9877 and send on 1235
localhost is used as IP for both.
"""
if __name__=="__main__":
  osc = OSC()
