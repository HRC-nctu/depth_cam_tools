#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 28 11:16:38 2014

@author: Antoine Hoarau <hoarau.robotics@gmail.com>
"""
import time
import ros_image_subscriber as rib
import numpy as np
from geometry_msgs.msg import PointStamped
import tf
import rospy
from threading import Thread
from sensor_msgs.msg import CameraInfo
import cv2
#from camera_info_manager import *

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
    
class Kinect:
    def __init__(self,camera_name='/camera',queue_size=1,compression=True,use_depth_registered=True,use_rect=True,use_ir=False):
        try:
            rospy.node_init("depth_sensor",anoymous=True)
        except: pass
    
        if not camera_name[0]=="/":
            camera_name = "/"+camera_name
        self.camera_name = camera_name
        # Waiting for service to be available, like the camera calibrator
        
        camera_info_service = get_output_list("rosservice list | grep "+camera_name+" | grep set_camera_info",timeout=30.0)[0]
        rospy.loginfo(self.camera_name+" waiting for "+camera_info_service)
        rospy.wait_for_service(camera_info_service,timeout=30.0)
        # tests with camera_info manager
        #file_url = ''
        #try : 
        #    file_url = rospy.get_param(camera_name+'/driver/depth_camera_info_url')
        #except : pass
        #depth_info = CameraInfoManager(cname=camera_name[1:],url=file_url)#,url="file://${ROS_HOME}/camera_info/${NAME}.yaml")
        #depth_info.loadCameraInfo()
        #rgb_info = CameraInfoManager.__init__(self,"rgb_"+camera_name)
        #print "Camera:",depth_info.getCameraName()
        #print "URL:",depth_info.getURL()
        #print "Calib:",depth_info.getCameraInfo()
        ## Should be use rectified images ?
        self.use_depth_registered = use_depth_registered
        self.use_ir = use_ir
        
        depth="depth"
        if use_depth_registered:
            depth = "depth_registered"
            
        rect=""
        if use_rect:
            rect="_rect"
        
        # Temporary solution for OPENNI2/1 compatibility (it adds sw and hw_registered in the topi names)
        #For now, topic are listed in alphabetical order, so the shortest is the right one !
        ## Topics
        #####################rgb_topic   = get_output_list("rostopic list | grep "+camera_name+" | grep rgb | grep image"+rect,timeout=5.0)

        #####################depth_topic = get_output_list("rostopic list | grep "+camera_name+" | grep "+depth+" | grep image"+rect,timeout=5.0)
        
        self.rgb_topic      = camera_name+'/rgb/image'+rect+'_color' #rgb_topic[0]
        
        if use_depth_registered:
            self.depth_topic    = camera_name+'/'+depth+'/hw_registered'+'/image'+rect+"_raw" #depth_topic[0]    
        else:
            self.depth_topic    = camera_name+'/'+depth+'/image'+rect+'_raw' #depth_topic[0]
        
        #depth_registered_topic = camera_name+'/depth_registered/image'+rect
        if use_rect:
            self.ir_topic    = camera_name+'/ir/image_rect_ir'
        else:
            self.ir_topic    = camera_name+'/ir/image_raw'
            
        ## Frames
        self.depth_optical_frame    = camera_name+'_depth_optical_frame'
        self.link_frame             = camera_name+'_link'
        self.depth_frame            = camera_name+'_depth_frame'
        self.rgb_frame              = camera_name+'_rgb_frame'
        self.rgb_optical_frame      = camera_name+'_rgb_optical_frame'

        ## Get Intrinsics
        self.depth_camera_info=self.get_camera_info(camera_name,'depth')
        self.depth_th = rib.ROSImageSubscriber(self.depth_topic,queue_size=queue_size,use_compression=compression)        
        #self.depth_registered_th = rib.ROSImageSubscriber(depth_registered_topic,queue_size=queue_size,use_compression=compression)        
        self.depth_th.start()
        #self.depth_registered_th.start()
        
        if not self.use_ir:
            self.rgb_camera_info=self.get_camera_info(camera_name,'rgb')
            self.rgb_th = rib.ROSImageSubscriber(self.rgb_topic,queue_size=queue_size,use_compression=compression)
            self.rgb_th.start()
        else:
            self.ir_camera_info=self.get_camera_info(camera_name,'depth')
            self.ir_th = rib.ROSImageSubscriber(self.ir_topic,queue_size=queue_size,use_compression=compression)
            self.ir_th.start()
                        
        self.tf = tf.TransformListener()
        #self.cloud_event = Event()
    def get_camera_info_url(self,camera_name,img_name='depth'):
        return rospy.get_param(camera_name+'/driver/'+img_name+'_camera_info_url').replace('file://','')
        
    def get_camera_info(self,camera_name,img_name='depth'):
        import yaml
        import os
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

    def mouse_callback_spin_once(self):
        self.depth_th.mouse_callback_spin_once()        
        #self.depth_registered_th.mouse_callback_spin_once()
        if not self.use_ir:
            self.rgb_th.mouse_callback_spin_once()
        else:
            self.rgb_th.mouse_callback_spin_once()        

    def register_mouse_callbacks(self,function):
        self.depth_th.register_mouse_callback(function)
        #self.depth_registered_th.register_mouse_callback(function)        
        if not self.use_ir:
            self.rgb_th.register_mouse_callback(function)
        else:
            self.ir_th.register_mouse_callback(function)              

    def get_rgb_window_name(self):
        return self.rgb_th.get_window_name()

    def get_ir_window_name(self):
        return self.ir_th.get_window_name()

    def get_depth_window_name(self):
        #if self.use_depth_registered:
        #    return self.depth_registered_th.get_window_name()
        #else:
        return self.depth_th.get_window_name()
            
    def release(self):
        self.release_depth()
        if not self.use_ir:
            self.release_rgb()
        else:
            self.release_ir()
        

    def locked(self):
        if not self.use_ir:            
            return self.rgb_th.locked() or self.depth_th.locked()
        else:
            return self.ir_th.locked() or self.depth_th.locked()

    def lock(self):
        self.lock_depth()        
        if not self.use_ir:
            self.lock_rgb()        
        else:        
            self.lock_ir()

    def lock_rgb(self):
        self.rgb_th.lock()
        
    def lock_ir(self):
        self.ir_th.lock()

    def lock_depth(self):
        #if self.use_depth_registered:
        #    self.depth_registered_th.lock()
        #else:
        self.depth_th.lock()

    def release_rgb(self):
        self.rgb_th.release()
        
    def release_ir(self):
        self.ir_th.release()

    def release_depth(self):
        #if self.use_depth_registered:
        #    self.depth_registered_th.release()
        #else:
        self.depth_th.release()

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
        
    def get_closest_pt2d(self,pt3d,list_pt2d=None):
        if not isinstance(pt3d,list):
            pt3d = np.asarray(pt3d)

        depth = self.get_depth()
        pmin_all=np.empty((len(pt3d),2))

        dmin_all=[np.inf]*len(pt3d)
        #cloud = np.empty((depth.shape[0],depth.shape[1],3)
        #n=depth.shape[0]*depth.shape[1]
        for i in xrange(depth.shape[0]):
            for j in xrange(depth.shape[1]):
                if self.cloud_event.is_set():
                    print "Cancelling current process"
                    return []
                p = [self.depth_to_world(i,j,depth,transform_to_camera_link=True)]*len(pt3d)
                dall = np.apply_along_axis(np.linalg.norm, 1, pt3d-p)
                for k in xrange(len(dall)):
                    if dall[k]<dmin_all[k]:
                        dmin_all[k] = dall[k]
                        pmin_all[k] = [i,j]
            #print i*depth.shape[1]*100/n,"%"
        if not list_pt2d:
            return pmin_all
        else:
            list_pt2d = pmin_all

    def world_to_depth(self,pt,use_distortion=True):
        if not self.use_ir:
            projMatrix = np.matrix(self.rgb_camera_info.P).reshape(3,4)
            distCoeffs = np.matrix(self.rgb_camera_info.D)
        else:
            projMatrix = np.matrix(self.ir_camera_info.P).reshape(3,4)
            distCoeffs = np.matrix(self.ir_camera_info.D)
            
        cameraMatrix, rotMatrix, tvec, _, _, _, _ = cv2.decomposeProjectionMatrix(projMatrix)
        
        rvec,_ = cv2.Rodrigues(rotMatrix)
        
        if not use_distortion:
            distCoeffs = np.array([])
        imgpoints2, _ = cv2.projectPoints(np.array([pt]), rvec, np.zeros(3),cameraMatrix, distCoeffs)

        result = imgpoints2[0][0]
        return result

    
    def __color_to_world__(self,x,y):# DEPRECATED
         fx_rgb = self.rgb_camera_info.K[0]
         fy_rgb = self.rgb_camera_info.K[4]
         cx_rgb = self.rgb_camera_info.K[2]
         cy_rgb = self.rgb_camera_info.K[5]

         v = self.depth_to_world(x, y)
         v[0] = (v[0]/9.9984628826577793e-01) - 1.9985242312092553e-02
         v[1] = (v[1]/9.9984628826577793e-01)
         v[2] = (v[2]/9.9984628826577793e-01) - 1.9985242312092553e-02
         result = [np.nan]*3
         result[0] = (v[0]*fx_rgb/v[2])+cx_rgb;
         result[1] = (v[1]*fy_rgb/v[2])+cy_rgb;
         result[2] = v[2];
         return result;

    def raw_depth_to_meters(self, depth_value):
        # We use depth_registered so useless function
        if depth_value < 2047:
            return 1.0 / (depth_value * -0.0030711016 + 3.3309495161)
        return 0.0

    def depth_to_world(self,x,y,depth_img=None,transform_to_camera_link=True):
        if not self.use_ir:
            projMatrix = np.matrix(self.rgb_camera_info.P).reshape(3,4)
        else:
            projMatrix = np.matrix(self.ir_camera_info.P).reshape(3,4)
            
        cameraMatrix, rotMatrix, transVect, rotMatrixX, rotMatrixY, rotMatrixZ, eulerAngles = cv2.decomposeProjectionMatrix(projMatrix)
        
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

    def is_ready(self):
        if self.use_depth_registered:
            if self.use_ir:
                return self.ir_th.has_received_first[0] and self.depth_th.has_received_first[0]  #and (self.depth_registered_th.has_received_first[0] or self.depth_th.has_received_first[0])
            else:
                return self.rgb_th.has_received_first[0] and self.depth_th.has_received_first[0]  #and (self.depth_registered_th.has_received_first[0] or self.depth_th.has_received_first[0])
        else:
            if self.use_ir:
                return self.ir_th.has_received_first[0]
            else:
                return self.rgb_th.has_received_first[0]
            
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
            time.sleep(1.0)
        rospy.loginfo(self.camera_name+' ready !')
        
    def wait_until_ready(self,timeout=5.0):
        th = Thread(target=self.__wait_until_ready)
        th.start()
        th.join(timeout=timeout)

    def get_rgb(self,blocking=True):
        return self.rgb_th.get_image(blocking=blocking)
        
    def get_ir(self,blocking=True):
        return self.ir_th.get_image(blocking=blocking)

    def get_depth(self,blocking=True):
        #if self.use_depth_registered:
            #return self.get_depth_registered(blocking=blocking)
        #else:
        return self.depth_th.get_image(blocking=blocking)

    #def get_depth_registered(self,blocking=True):
    #    return self.depth_registered_th.get_image(blocking=blocking)

    def show_rgb(self):
        self.rgb_th.show()
        
    def show_ir(self):
        self.ir_th.show()

    def show_depth(self):
        self.depth_th.show()
        #if self.use_depth_registered:
        #    self.show_depth_registered()
        #else:
        #    if self.depth_th.has_received_first[0]:
        #        self._show_depth()

    #def show_depth_registered(self):
    #    if self.depth_registered_th.has_received_first[0]:
     #       self._show_depth_registered()

    #def _show_depth(self):
    #    self.depth_th.show()

    #def _show_depth_registered(self):
        #self.depth_registered_th.show()

    def is_alive(self):
        if self.use_depth_registered:    
            if self.use_ir:
                return self.ir_th.is_alive() or self.depth_th.is_alive() # or self.depth_registered_th.is_alive()
            else:
                return self.rgb_th.is_alive() or self.depth_th.is_alive() # or self.depth_registered_th.is_alive()
        else:
            if self.use_ir:
                return self.ir_th.is_alive()
            else:
                return self.rgb_th.is_alive()
            

    def stop(self):
        #self.depth_registered_th.stop()
        self.depth_th.stop()
        self.rgb_th.stop()
        self.ir_th.stop()
