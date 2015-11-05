# -*- coding: utf-8 -*-
"""
Created on Tue Nov  3 16:54:36 2015

@author: jimmy
"""
from abc import ABCMeta, abstractmethod
import rospy
import numpy as np
import ros_image_subscriber as rib
from geometry_msgs.msg import PointStamped
import tf
from threading import Thread
from sensor_msgs.msg import CameraInfo
import cv2
import yaml
import os
import time

def get_output_list(cmd,timeout=None):
    import subprocess,time
    output  = []
    start = time.time()
    while not output:
        try:
            output = subprocess.check_output(cmd, shell=True,universal_newlines=True).split('\n')
        except:
            if timeout:
                if time.time() - start > timeout:
                    break
                else:
                    time.sleep(0.1)
            else:
                break
    return list(filter(None, output))

class RGBDSensorAbstract:
    __metaclass__ = ABCMeta
    
    @classmethod
    def __init__(self, camera_name, rgb_topic = '', depth_topic = '', ir_topic = '', use_depth_registered = False, queue_size=1, compression=False):
    
        if not camera_name[0]=="/":
            camera_name = "/"+camera_name
        self.camera_name = camera_name
        
        # Waiting for service to be available, like the camera calibrator 
        camera_info_service = get_output_list("rosservice list | grep "+camera_name+" | grep set_camera_info",timeout=10.0)[0]
        rospy.loginfo(self.camera_name+" waiting for "+camera_info_service)
        rospy.wait_for_service(camera_info_service,timeout=10.0)

        self.use_rgb = False
        if rgb_topic is not '':
            self.use_rgb = True
            
        self.use_depth = False
        if depth_topic is not '':
            self.use_depth = True

        self.use_ir = False
        if ir_topic is not '':
            self.use_ir = True
            
        self.use_depth_registered = use_depth_registered
        
        ## Topics
        self.rgb_topic = rgb_topic
        self.depth_topic = depth_topic
        self.ir_topic = ir_topic
            
        ## Frames
        self.depth_optical_frame = camera_name+'_depth_optical_frame'
        self.link_frame = camera_name+'_link'
        self.rgb_optical_frame = camera_name+'_rgb_optical_frame'

        ## Get Intrinsics
        if self.use_depth:
            self.depth_camera_info=self.get_camera_info(camera_name,'depth')
            self.depth_th = rib.ROSImageSubscriber(self.depth_topic,queue_size=queue_size,use_compression=compression)        
            self.depth_th.start()
        if self.use_rgb:
            self.rgb_camera_info=self.get_camera_info(camera_name,'rgb')
            self.rgb_th = rib.ROSImageSubscriber(self.rgb_topic,queue_size=queue_size,use_compression=compression)
            self.rgb_th.start()
        if self.use_ir:
            self.ir_camera_info=self.get_camera_info(camera_name,'depth')
            self.ir_th = rib.ROSImageSubscriber(self.ir_topic,queue_size=queue_size,use_compression=compression)
            self.ir_th.start()
                        
        self.tf = tf.TransformListener()
        
    @classmethod
    @abstractmethod
    def get_camera_info_url(self,camera_name,img_name='depth'):
        return rospy.get_param(camera_name+'/driver/'+img_name+'_camera_info_url').replace('file://','')
    
    @classmethod
    @abstractmethod
    def get_camera_info(self,camera_name,img_name='depth'):
        camera_info = CameraInfo()
        file_url = ''
        try : 
            file_url = self.get_camera_info_url(camera_name,img_name)
        except Exception,e: print e
                
        if not os.path.exists(file_url):
            if img_name == 'depth':
                camera_info.K = np.array([610.183545355666, 0, 331.498179304952, 0, 610.613748569717, 257.128224589741, 0, 0, 1])
                camera_info.D = np.array([-0.0388664532195436, 0.111397388172138, 0.00673931006062305, 0.00762574500287458, 0])
                camera_info.P =  np.matrix([613.005981445312, 0, 334.904565660545, 0, 0, 614.685424804688, 259.144825464584, 0, 0, 0, 1, 0])
            elif img_name == 'rgb':
                camera_info.K = np.matrix([525.547200081387, 0, 317.00975850542, 0, 526.063977479593, 231.501564568755, 0, 0, 1])
                camera_info.D = np.array([0.0387333787967748, -0.11681772942717, -0.000993968071341523, 0.007556327027684, 0])
                camera_info.P =  np.matrix([523.705688476562, 0, 320.996738034948, 0, 0, 527.902526855469, 230.533531720312, 0, 0, 0, 1, 0])

            rospy.logwarn( "No camera info found at url ["+file_url+"], using default values.\n Consider setting the *_info_url")
            return camera_info
    
        print 'Loading camera '+img_name+' info at:',file_url
        with open(file_url, 'r') as f:
            calib = yaml.safe_load(f.read())
            camera_info.K = np.matrix(calib["camera_matrix"]["data"])
            camera_info.D = np.array(calib["distortion_coefficients"]["data"])
            camera_info.R = np.matrix(calib["rectification_matrix"]["data"])
            camera_info.P = np.matrix(calib["projection_matrix"]["data"])
            camera_info.height = calib["image_height"]
            camera_info.width = calib["image_width"]
            print camera_info
        return camera_info

    @classmethod
    @abstractmethod
    def mouse_callback_spin_once(self):
        if self.use_depth:
            self.depth_th.mouse_callback_spin_once()        
        if self.use_ir:
            self.ir_th.mouse_callback_spin_once()
        if self.use_rgb:
            self.rgb_th.mouse_callback_spin_once()        

    @classmethod
    @abstractmethod
    def register_mouse_callbacks(self,function):
        if self.use_depth:
            self.depth_th.register_mouse_callback(function)
        if self.use_ir:
            self.ir_th.register_mouse_callback(function)
        if self.use_rgb:
            self.rgb_th.register_mouse_callback(function)              

    @classmethod
    @abstractmethod
    def transform_point(self,numpoint,target_frame,source_frame):
        p = PointStamped()
        p.header.frame_id = source_frame
        p.point.x = numpoint[0]
        p.point.y = numpoint[1]
        p.point.z = numpoint[2]
        p_out = [np.nan]*3
        try:
            self.tf.waitForTransform(target_frame,source_frame,rospy.Time(0),rospy.Duration(5.0))
            geo_out = self.tf.transformPoint(target_frame, p).point
            p_out = np.array([ geo_out.x,geo_out.y,geo_out.z])
        except tf.Exception,e:
            print e

        return p_out
        
    @classmethod
    @abstractmethod
    def world_to_depth(self,pt,use_distortion=True):
        projMatrix = np.matrix(self.depth_camera_info.P).reshape(3,4)
        distCoeffs = np.matrix(self.depth_camera_info.D)
        cameraMatrix, rotMatrix, tvec, _, _, _, _ = cv2.decomposeProjectionMatrix(projMatrix)
        rvec,_ = cv2.Rodrigues(rotMatrix)
        
        if not use_distortion:
            distCoeffs = np.array([])
        imgpoints2, _ = cv2.projectPoints(np.array([pt]), rvec, np.zeros(3),cameraMatrix, distCoeffs)

        result = imgpoints2[0][0]
        return result
    
    @classmethod
    @abstractmethod
    def world_to_ir(self,pt,use_distortion=True):
        projMatrix = np.matrix(self.ir_camera_info.P).reshape(3,4)
        distCoeffs = np.matrix(self.ir_camera_info.D)
        cameraMatrix, rotMatrix, tvec, _, _, _, _ = cv2.decomposeProjectionMatrix(projMatrix)
        rvec,_ = cv2.Rodrigues(rotMatrix)
        
        if not use_distortion:
            distCoeffs = np.array([])
        imgpoints2, _ = cv2.projectPoints(np.array([pt]), rvec, np.zeros(3),cameraMatrix, distCoeffs)

        result = imgpoints2[0][0]
        return result
    
    @classmethod
    @abstractmethod
    def world_to_rgb(self,pt,use_distortion=True):
        projMatrix = np.matrix(self.rgb_camera_info.P).reshape(3,4)
        distCoeffs = np.matrix(self.rgb_camera_info.D)
        cameraMatrix, rotMatrix, tvec, _, _, _, _ = cv2.decomposeProjectionMatrix(projMatrix)
        rvec,_ = cv2.Rodrigues(rotMatrix)
        
        if not use_distortion:
            distCoeffs = np.array([])
        imgpoints2, _ = cv2.projectPoints(np.array([pt]), rvec, np.zeros(3),cameraMatrix, distCoeffs)

        result = imgpoints2[0][0]
        return result
        
    @classmethod
    @abstractmethod
    def depth_to_world(self,x,y,depth_img=None,transform_to_camera_link=True):
        cameraMatrix = np.matrix(self.depth_camera_info.K).reshape(3,3)
        
        fx_d = cameraMatrix[0,0]
        fy_d = cameraMatrix[1,1]
        cx_d = cameraMatrix[0,2]
        cy_d = cameraMatrix[1,2]

        if depth_img is None:
            depth_img = self.get_depth()
        result = [np.nan]*3
        
        try:
            if depth_img is not None:
                z = (depth_img[y][x])[0]/1000.0
                if (z == 0):
                    return [np.nan]*3
                              
                result = [(x - cx_d) * z / fx_d ,(y - cy_d) * z / fy_d, z ]
        except Exception,e: 
            print e
            
        if transform_to_camera_link:
            if not self.use_depth_registered:
                return self.transform_point(result,self.link_frame,self.depth_optical_frame)
            else:
                return self.transform_point(result,self.link_frame,self.rgb_optical_frame)
        else:
            return np.array(result)
    
    @classmethod
    @abstractmethod        
    def ir_to_world(self,x,y,ir_img=None,transform_to_camera_link=True):
        cameraMatrix = np.matrix(self.ir_camera_info.K).reshape(3,3)
        
        fx_d = cameraMatrix[0,0]
        fy_d = cameraMatrix[1,1]
        cx_d = cameraMatrix[0,2]
        cy_d = cameraMatrix[1,2]

        if ir_img is None:
            ir_img = self.get_ir()
        result = [np.nan]*3
        
        try:
            if ir_img is not None:
                z = (ir_img[y][x])[0]/1000.0
                if (z == 0):
                    return [np.nan]*3
                              
                result = [(x - cx_d) * z / fx_d ,(y - cy_d) * z / fy_d, z ]
        except Exception,e: 
            print e
            
        if transform_to_camera_link:
            return self.transform_point(result,self.link_frame,self.depth_optical_frame)
        else:
            return np.array(result)
    
    @classmethod
    @abstractmethod       
    def rgb_to_world(self,x,y,rgb_img=None,transform_to_camera_link=True):
        cameraMatrix = np.matrix(self.rgb_camera_info.K).reshape(3,3)
        
        fx_d = cameraMatrix[0,0]
        fy_d = cameraMatrix[1,1]
        cx_d = cameraMatrix[0,2]
        cy_d = cameraMatrix[1,2]

        if rgb_img is None:
            rgb_img = self.get_rgb()
        result = [np.nan]*3
        
        try:
            if rgb_img is not None:
                z = (rgb_img[y][x])[0]/1000.0
                if (z == 0):
                    return [np.nan]*3
                              
                result = [(x - cx_d) * z / fx_d ,(y - cy_d) * z / fy_d, z ]
        except Exception,e: 
            print e
            
        if transform_to_camera_link:
            return self.transform_point(result,self.link_frame,self.rgb_optical_frame)
        else:
            return np.array(result)
            
    @classmethod
    @abstractmethod
    def is_ready(self):
        if (self.use_ir and not self.ir_th.has_received_first[0]):
            return False
        if (self.use_depth and not self.depth_th.has_received_first[0]):
            return False
        if (self.use_rgb and not self.rgb_th.has_received_first[0]):
            return False
        return True
    
    @classmethod
    @abstractmethod
    def is_alive(self):
        if (self.use_ir and not self.ir_th.is_alive()):
            return False
        if (self.use_depth and not self.depth_th.is_alive()):
            return False
        if (self.use_rgb and not self.rgb_th.is_alive()):
            return False
        return True
    

    @classmethod
    def __wait_until_ready(self):
        while not self.is_ready() and self.is_alive():
            if not self.use_ir:
                if not self.rgb_th.has_received_first[0]:
                    rospy.loginfo(self.camera_name+' waiting for '+self.rgb_topic+' to be ready')
            else:
                if not self.ir_th.has_received_first[0]:
                    rospy.loginfo(self.camera_name+' waiting for '+self.ir_topic+' to be ready')
            if not self.depth_th.has_received_first[0]:
                rospy.loginfo(self.camera_name+' waiting for '+self.depth_topic+' to be ready')
            time.sleep(1.)
        rospy.loginfo(self.camera_name+' ready !')
    
    @classmethod
    @abstractmethod
    def wait_until_ready(self,timeout=5.0):
        th = Thread(target=self.__wait_until_ready)
        th.start()
        th.join(timeout=timeout)

    @classmethod
    @abstractmethod
    def get_rgb(self,blocking=True):
        return self.rgb_th.get_image(blocking=blocking)
    
    @classmethod
    @abstractmethod    
    def get_ir(self,blocking=True):
        return self.ir_th.get_image(blocking=blocking)
        
    @classmethod
    @abstractmethod
    def get_depth(self,blocking=True):
        return self.depth_th.get_image(blocking=blocking)

    @classmethod
    @abstractmethod
    def show_rgb(self):
        self.rgb_th.show()

    @classmethod
    @abstractmethod        
    def show_ir(self):
        self.ir_th.show()
        
    @classmethod
    @abstractmethod
    def show_depth(self):
        self.depth_th.show()

    @classmethod
    @abstractmethod            
    def stop(self):
        if self.use_depth:
            self.depth_th.stop()     
        if self.use_ir:
            self.ir_th.stop()
        if self.use_rgb:
            self.rgb_th.stop()

    @classmethod
    @abstractmethod
    def release(self):
        if self.use_depth:
            self.release_depth()    
        if self.use_ir:
            self.release_ir()  
        if self.use_rgb:
            self.release_rgb()                

    @classmethod
    @abstractmethod
    def locked(self):
        if (self.use_ir and self.ir_th.locked()):
            return True
        if (self.use_depth and self.depth_th.locked()):
            return True
        if (self.use_rgb and self.rgb_th.locked()):
            return True
        return False    

    @classmethod
    @abstractmethod
    def lock(self):
        if self.use_depth:
            self.lock_depth()    
        if self.use_ir:
            self.lock_ir()  
        if self.use_rgb:
            self.lock_rgb() 

    @classmethod
    @abstractmethod
    def lock_rgb(self):
        self.rgb_th.lock()

    @classmethod
    @abstractmethod        
    def lock_ir(self):
        self.ir_th.lock()

    @classmethod
    @abstractmethod
    def lock_depth(self):
        self.depth_th.lock()

    @classmethod
    @abstractmethod
    def release_rgb(self):
        self.rgb_th.release()

    @classmethod
    @abstractmethod        
    def release_ir(self):
        self.ir_th.release()

    @classmethod
    @abstractmethod
    def release_depth(self):
        self.depth_th.release()