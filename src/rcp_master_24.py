#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import math
import sys
import rospy
import rosparam
import roslib
import os
import smach
import smach_ros
import pickle
from std_msgs.msg import Float64
from happymimi_msgs.srv import SimpleTrg, StrTrg
from happymimi_navigation.srv import NaviLocation, NaviCoord
from happymimi_recognition_msgs.srv import RecognitionFind,RecognitionFindRequest,RecognitionLocalize,RecognitionLocalizeRequest,MultipleLocalize
from base_control import BaseControl
from recognition_tools import RecognitionTools 
from happymimi_recognition_msgs.srv import Clip, ClipResponse

import sp_receptionist as sp

teleop_path = roslib.packages.get_pkg_dir('recognition_processing')
sys.path.insert(0, os.path.join(teleop_path, 'src/'))

file_path = roslib.packages.get_pkg_dir('happymimi_teleop') + '/src/'
sys.path.insert(0, file_path)

# speak
tts_srv = rospy.ServiceProxy('/tts', StrTrg)
# wave_play
wave_srv = rospy.ServiceProxy('/waveplay_srv', StrTrg)
pickle_path = "/home/mimi/main_ws/src/receptionist/config/guest_feature.pkl"
rt = RecognitionTools()

with open(pickle_path , "wb") as f:
    feature_dic = {"guest1":{"name":"","drink":"","age":""},
                "guest2":{"name":"","drink":"","age":""}}
    pickle.dump(feature_dic, f)

RANGE = 3

class MoveInitalPosition(smach.State):#ゲストの検出のための位置へ移動
    def __init__(self):
        smach.State.__init__(self,outcomes = ['move_finish'],
                             input_keys = ['g_count_in']
                             )
        self.gen_coord_srv = rospy.ServiceProxy('/human_coord_generator', SimpleTrg)
        #self.ap_srv = rospy.ServiceProxy('/approach_person_server', StrTrg)
        self.navi_srv = rospy.ServiceProxy('navi_location_server', NaviLocation)
        self.head_pub = rospy.Publisher('/servo/head',Float64, queue_size = 1)
        self.bc = BaseControl()

    def execute(self,userdata):
        rospy.loginfo("Executing state:MOVE_INITAL_POSITION")
        guest_num = userdata.g_count_in
        
        if guest_num == 0:
           #dooropen
            tts_srv("start receptionist")
            return 'move_finish'
            #pass
        if guest_num == 1:

            self.navi_srv('entrance')
            #self.bc.rotateAngle(,0.2)#入り口の方を向く
            rospy.sleep(3.5)
            return 'move_finish'

class DiscoverGuests(smach.State):#ゲストの検出、受付
    def __init__(self):
        smach.State.__init__(self, outcomes = ['discover_finish'],
                             output_keys = ['feature_out']
                             )
        self.ap_srv = rospy.ServiceProxy('/approach_person_server', StrTrg)
        #self.head_pub = rospy.ServiceProxy('/servo/head',Float64, queue_size = 1)
        self.find_srv = rospy.ServiceProxy('/recognition/find',RecognitionFind)
        self.head_pub = rospy.Publisher('/servo/head', Float64, queue_size = 1)
        self.age_srv = rospy.ServiceProxy('/person_feature/gpt',Clip)


    def execute(self,userdata):
        rospy.loginfo("Executing state:DISCOVERGUESTS")
        self.head_pub.publish(-15)
        rospy.sleep(1.0)
        #人の検知
        while(1):
            self.find_result = self.find_srv(RecognitionFindRequest(target_name = 'person')).result
            rospy.sleep(1.0)
            if self.find_result == True:
                print('found a person')
                req  = RecognitionLocalizeRequest()
                req.target_name  = "person"
                #rt = RecognitionTools()
                centroid = rt.localizeObject(request = req).point
                person_height = centroid.z
                self.head_pub.publish(-10)
                rospy.sleep(1.0)
                #self.head_pub.publish(20)
                #rospy.sleep(1.0)
                wave_srv('/receptionist/hello.wav')
                rospy.sleep(0.5)
                get_feature = sp.GetFeature()
                name = get_feature.getName()
                drink = get_feature.getFavoriteDrink()
                #age = str(self.age_srv("age"))#画像認識で可能なら要変更

                #####
                age = str(self.age_srv("age"))#いらない？
                self.f_age = str("Age is" + self.getAge())

                a = str(self.per_fea_srv("glass"))
                self.f_glass = a.replace("result: a photo of ", "")

                b = str(self.per_fea_srv("gender"))
                self.f_gender = a.replace("result: a photo of ", "")

                self.f_cloth = str(self.per_fea_srv("cloth"))

                self.f_pants = str(self.per_fea_srv("pants"))

                feature_list = [self.f_age, self.f_glass, self.f_gender, self.f_cloth, self.f_pants]
                #書き換える
                userdata.feature_out = feature_list

                #initにoutput_keys = ['feature_out']がいる



                #####

                age_int = re.findall('[0-9]+', age)
                get_feature.getAge(age_int[0])
                wave_srv("/receptionist/thank.wav")
                rospy.sleep(0.5)
                break

            elif(self.find_result==False):
                #print("found a person")
                tts_srv("i wait person")
                rospy.sleep(3.0)
                continue

        return 'discover_finish'

class IntroduceGuests(smach.State):#オーナーのもとへ移動、ゲストの紹介
    def __init__(self):
        smach.State.__init__(self, outcomes = ['introduce_finish'],
                             input_keys = ['g_count_in']
                             )
        self.navi_srv = rospy.ServiceProxy('navi_location_server', NaviLocation)
        self.arm_srv = rospy.ServiceProxy('/servo/arm', StrTrg)
        self.bc = BaseControl()
        self.save_srv = rospy.ServiceProxy('/recognition/save',StrTrg)
        self.multiple = rospy.ServiceProxy('/recognition/multiple_localize',MultipleLocalize)
        self.sentence_list = []
        self.coord_gen_srv = rospy.ServiceProxy('/human_coord_generator',SimpleTrg)
        self.ap_srv = rospy.ServiceProxy('/approach_person_server', StrTrg)

    def execute(self,userdata):
        rospy.loginfo("Executing state:INTRODUCE_GUESTS")
        tts_srv("please follow me.")
        rospy.sleep(1.0)
        guest_num = userdata.g_count_in
        self.bc.rotateAngle(-150,0.3)
        rospy.sleep(1.0)
        g_name = "human_0"
        result = self.coord_gen_srv().result
        print("result")
        print(result)
        self.ap_srv(data = g_name)
        '''
        self.navi_srv('operator')
        rospy.sleep(1.0)
        #ゲストの方を指す
        #ゲストの位置が分からないからアングルの角度がわからない
        '''
        tts_srv("We'll start introducing our guests.")
        introduce = sp.IntroduceOfGuests()
        #introduce.main(guest_num)
        #self.bc.rotateAngle(150,0.3)
        rospy.sleep(0.5)
        self.bc.rotateAngle(180,0.3)
        chair_points = self.multiple("person").points
        if chair_points:
            chair_points = str(chair_points[0]).split()
            print(chair_points)
            chair_x = float(chair_points[1])
            chair_y = float(chair_points[3])
            angle = math.atan2(chair_y,chair_x) * (180/ math.pi)
            rospy.sleep(1.0)
            self.bc.rotateAngle(int(angle),0.2)
        rospy.sleep(1.0)
        self.arm_srv('point')
        rospy.sleep(5.0)
        introduce.main(guest_num)
        rospy.sleep(1.0)
        self.arm_srv('carry')
        rospy.sleep(5.0)
        return 'introduce_finish'

class GuideGuests(smach.State):#ゲストのガイド
    def __init__(self):
        smach.State.__init__(self, outcomes = ['guide_finish','all_finish'],
                             input_keys = ['g_count_in', 'feature_in'],
                             output_keys =  ['g_count_out'])
        self.bc = BaseControl()
        self.arm_srv = rospy.ServiceProxy('/servo/arm', StrTrg)
        self.navi_srv = rospy.ServiceProxy('navi_location_server', NaviLocation)
        self.head_pub =rospy.Publisher('/servo/head', Float64, queue_size=1)
        self.localize =rospy.ServiceProxy('/recognition/localize', RecognitionLocalize)
        self.multiple = rospy.ServiceProxy('/recognition/multiple_localize',MultipleLocalize)
        #self.guide = GuideGuests()

        self.tts_srv = rospy.ServiceProxy('/tts', StrTrg)

    def execute(self, userdata):
        with open(pickle_path,'rb') as f:
            self.feature_dic = pickle.load(f)
        rospy.loginfo("Executing state:GUIDE_GUESTS")
        print('dict:')
        print(self.feature_dic)
        guest_num = userdata.g_count_in
        rospy.sleep(2.0)
        tts_srv("plese follow me")
        rospy.sleep(1.0)
        self.navi_srv('order')
        rospy.sleep(2.0)


        
        while 1:
                chair_points = self.multiple("chair").points
                if chair_points:
                    print(chair_points)
                    
                    ########################


                    #人が座ってる席をなくす処理
                    

                    #########################
                        
                    angle = math.atan2(chair_y,chair_x) * (180/ math.pi)
                    rospy.sleep(1.0)
                    self.bc.rotateAngle(int(angle),0.2)

                    rospy.sleep(0.5)
                    self.arm_srv('point')
                    rospy.sleep(0.5)
                    wave_srv("/receptionist/sit.wav")#("Please sit in this chair.")
                    rospy.sleep(0.5)
                    guest_num += 1
                    rospy.sleep(1.0)
                    userdata.g_count_out = guest_num
                    self.arm_srv('carry')
                    rospy.sleep(5.0)

                    if guest_num == 0 :
                        return 'guide_finish'
                    
                    else:
                        self.sentence_list = userdata.feature_in
                        print(userdata.feature_in)

                        for i in range(len(self.sentence_list)):
                            self.tts_srv(self.sentence_list[i])
                            i += 1

                        tts_srv('finish receptionist')
                        return 'all_finish'
        
            
    def Calculate_Angle(chair_points,i):
        print(chair_points,"chair_num:" + str(i))
        chair_point = str(chair_points[i]).split()
        print(chair_points)
        chair_x = float(chair_point[1])
        chair_y = float(chair_point[3])
        return chair_x,chair_y
        
                    

if __name__ == '__main__':
    
    rospy.init_node('receptionist_master')
    rospy.loginfo("Start receptionist")
    sm_top = smach.StateMachine(outcomes = ['finish_sm_top'])
    sm_top.userdata.guest_count = 0
    with sm_top:
        smach.StateMachine.add(
                'MOVE_INITAL_POSITION',
                MoveInitalPosition(),
                transitions = {'move_finish':'DISCOVERGUESTS_GUEST'},
                remapping = {'g_count_in':'guest_count'})

        smach.StateMachine.add(
                'DISCOVERGUESTS_GUEST',
                DiscoverGuests(),
                transitions = {'discover_finish':'INTRODUCE_GUESTS'},
                remapping = {'g_count_in':'guest_count'})

        smach.StateMachine.add(
                'INTRODUCE_GUESTS',
                IntroduceGuests(),
                transitions = {'introduce_finish':'GUIDE_GUESTS'},
                remapping = {'future_out':'guest_future',
                             'g_count_in':'guest_count'})

        smach.StateMachine.add(
                'GUIDE_GUESTS',
                GuideGuests(),
                transitions = {'guide_finish':'MOVE_INITAL_POSITION',
                               'all_finish':'finish_sm_top'},
                remapping = {'g_count_in':'guest_count',
                             'g_count_out':'guest_count'})

    outcome = sm_top.execute()
 
#rosrun person_feature_extraction gpt2_exam_realsense.py 
