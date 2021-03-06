from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw
import HyperLPRLite as pr
import cv2
import dlib
import math
import datetime
import numpy as np



class Frame():
	def __init__(self, img, outputs, class_names, num_frame, trackers, labels, confidence, traffic_sta,
	             license_plate, fps, IfLicensePlate, IfTrafficLight, IfEstimateSpeed):
		self.trackers = trackers # 当前帧识别目标的坐标（左上角、右下角）
		self.labels = labels # position对应目标的标签
		self.confidence = confidence # 当前帧识别目标的置信度
		self.num_frame = num_frame # 当前是第几帧
		self.init_image = img # 当前帧原始图像
		self.traffic_sta = traffic_sta # 车流量统计
		self.license_plate = license_plate
		self.fps = fps

		# 功能选项
		self.IfLicensePlateRecognition = IfLicensePlate
		self.IfTrafficLightRecognition = IfTrafficLight
		self.IfEstimateSpeed = IfEstimateSpeed

		if self.num_frame%10 == 0:
			self.trackers = []
			self.labels = []
			self.confidence = []
			# 初始化当前帧识别出的目标
			boxes, objectness, classes, nums = outputs
			boxes, objectness, classes, nums = boxes[0], objectness[0], classes[0], nums[0]
			wh = np.flip(img.shape[0:2])
			for i in range(nums):
				if objectness[i] > 0.8:  # 仅保留confidence大于一定数值的目标
					label = class_names[int(classes[i])]
					if label=='person' or label=='car' or \
						label=='truck' or label=='bus' or label=='motorbike' or label=='traffic light':

						x1y1 = tuple((np.array(boxes[i][0:2]) * wh).astype(np.int32))
						x2y2 = tuple((np.array(boxes[i][2:4]) * wh).astype(np.int32))

						# 使用dlib进行目标追踪
						t = dlib.correlation_tracker()
						rect = dlib.rectangle(int(x1y1[0]), int(x1y1[1]),
						                      int(x2y2[0]), int(x2y2[1]))
						t.start_track(self.init_image, rect)
						# 保存结果
						self.trackers.append(t)
						self.labels.append(label)
						self.confidence.append(objectness[i])

		else:
			for i in range(len(self.trackers)): # 更新追踪器的同时统计流量数据、计算车速
				t = self.trackers[i]
				l = self.labels[i]
				if l[0:3]=='car' or l=='motorbike':
					pos_pre = t.get_position()
					t.update(self.init_image)
					pos_cur = t.get_position()

					# 获取追踪目标前一帧和后一帧的Y轴坐标
					startX_pre = pos_pre.left()
					startX_cur = pos_cur.left()
					startY_pre = pos_pre.top()
					startY_cur = pos_cur.top()
					if (startY_pre <= 350 and startY_cur > 350) or (startY_pre >= 350 and startY_cur < 350):
						self.traffic_sta += 1
					elif (startX_pre <= 600 and startX_cur > 600) or (startX_pre >= 600 and startX_cur < 600):
						self.traffic_sta += 1

					if l[0:3]=='car' and self.IfEstimateSpeed:
						self.labels[i] = 'car'
						speed = int(self.Estimate_Speed(pos_pre, pos_cur))
						self.labels[i] += " {}km/h".format(speed)



				else:
					t.update(self.init_image)


	def Get_Track_Obj(self):
		return self.trackers, self.labels, self.confidence, self.license_plate


	def Get_Traffic_Sta(self):
		return self.traffic_sta


	def Count_Obj(self): # 统计当前帧画面中的检测目标个数
		count_obj = {} # 存放不同检测目标的个数
		count_car = 0
		count_motorbike = 0
		count_person = 0
		obj_num = len(self.labels)  # 识别出的物体数量

		for i in range(obj_num):
			if self.labels[i][0:3] == 'car':
				count_car += 1
			elif self.labels[i] == 'motorbike':
				count_motorbike += 1
			elif self.labels[i] == 'person':
				count_person += 1

		count_obj['car'] = count_car
		count_obj['motorbike'] = count_motorbike
		count_obj['person'] = count_person

		return count_obj


	def License_plate_recognition(self, grr):
		global fontC
		fontC = ImageFont.truetype("./Font/platech.ttf", 16, 0)
		text = ""
		grr = cv2.resize(grr, (400, 400), interpolation=cv2.INTER_AREA)
		model = pr.LPR("model/cascade.xml", "model/model12.h5", "model/ocr_plate_all_gru.h5")

		for pstr, confidence, rect in model.SimpleRecognizePlateByE2E(grr):
			if confidence > 0.7:
				if len(pstr) > 7:
					pstr = pstr[0:7]
				text = pstr + "   " + str(round(confidence, 3))
				return text
		return text


	def Traffic_Light_Recognition(self, img_rgb):
		#cv2.imshow("1", img_rgb)
		img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
		H = img_hsv[:, :, 0]
		H = np.squeeze(np.reshape(H, (1, -1)))
		H_value = np.array([])

		for i in H:
			if i > 0 and i < 124:
				H_value = np.append(H_value, i)
		H_avg = int(np.average(H_value))
		#print(H_avg)
		# 判断颜色
		if H_avg <= 10 or H_avg >= 27:
			color = "Red"
		elif H_avg >= 11 and H_avg <= 19:
			color = "Yellow"
		elif H_avg >= 20 and H_avg <= 26:
			color = "Green"
		else:
			color = "Unkonwn"

		return color


	def Estimate_Speed(self, pos_pre, pos_cur, fps=60, my_speed=0):
		# location = [StartX, StartY, Width, Height]
		location1 = [int(pos_pre.left()), int(pos_pre.top()), int(pos_pre.right()) - int(pos_pre.left()),
		             int(pos_pre.bottom()) - int(pos_pre.top())]
		location2 = [int(pos_cur.left()), int(pos_cur.top()), int(pos_cur.right()) - int(pos_cur.left()),
		             int(pos_cur.bottom()) - int(pos_cur.top())]
		# center是前后标注框的中心点坐标 [X, Y]
		center_1 = [location1[0] + (location1[2]) / 2, location1[1] + (location1[3]) / 2]
		center_2 = [location2[0] + (location2[2]) / 2, location2[1] + (location2[3]) / 2]

		# 计算标注框中心移动的像素距离
		d_pixels = math.sqrt(math.pow(center_2[0] - center_1[0], 2) + math.pow(center_2[1] - center_1[1], 2))
		ppm = 150/1.7
		d_meters = d_pixels / ppm
		speed = (my_speed + d_meters * fps) * 3.6

		if speed <= 3:
			speed = 0
		return speed


	def Draw_Outputs(self):
		obj_num = len(self.labels) # 识别出的物体数量
		img = self.init_image.copy()

		for i in range(obj_num):
			pos = self.trackers[i].get_position()
			x1y1 = (int(pos.left()), int(pos.top()))
			x2y2 = (int(pos.right()), int(pos.bottom()))
			img = cv2.rectangle(img, x1y1, x2y2, (255, 0, 0), 2)

			if self.labels[i]=='truck' or self.labels[i]=='bus':
				self.labels[i] = 'car'

			if self.labels[i] == 'car':
				if self.IfLicensePlateRecognition and self.num_frame%30==0: # 识别车牌
					startX, endX = x1y1[0], x2y2[0]
					startY, endY = x1y1[1], x2y2[1]
					text = self.License_plate_recognition(self.init_image[startY:endY, startX:endX])
					if text != "":
						self.labels[i] = text
						self.license_plate.append(text)
						img = Image.fromarray(img)
						draw = ImageDraw.Draw(img)
						draw.text((startX+5, startY-22), text, (0, 0, 255), font=fontC)
						img = np.array(img)
						continue

			elif self.labels[i] == 'traffic light':
				if self.IfTrafficLightRecognition:
					startX, endX = x1y1[0], x2y2[0]
					startY, endY = x1y1[1], x2y2[1]
					text = self.Traffic_Light_Recognition(self.init_image[startY:endY, startX:endX])
					if text != "Unknown":
						img = cv2.putText(img, text, (x1y1[0], x1y1[1]-5),
						                  cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 2)
						continue

			elif self.labels[i] in self.license_plate:
				img = Image.fromarray(img)
				draw = ImageDraw.Draw(img)
				draw.text((x1y1[0]+5, x1y1[1]-22), self.labels[i], (0, 0, 255), font=fontC)
				img = np.array(img)
				continue

			img = cv2.putText(img, '{} {:.4f}'.format(
				self.labels[i], self.confidence[i]),
			                  (x1y1[0], x1y1[1]-5), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 2)
		return img


	def Draw_Obj(self, image, count_obj):
		fontB = ImageFont.truetype("./Font/platech.ttf", 24, 0)
		img = Image.fromarray(image)
		draw = ImageDraw.Draw(img)

		count_text = ""
		count_text += "实时路人数目：{}\n".format(count_obj['person'])
		count_text += "实时汽车数目：{}\n".format(count_obj['car'])
		count_text += "实时摩托车数目：{}\n".format(count_obj['motorbike'])
		count_text += "路段车流量统计：{}\n".format(self.traffic_sta)

		if self.IfLicensePlateRecognition:
			count_text += "\n实时车牌汇总：\n"
			for license in self.license_plate:
				count_text += (license+'\n')

		draw.text((1150, 6), count_text, font = fontB)
		imagex = np.array(img)
		return imagex


	def Write_Excel(self, worksheet, count_obj):
		row = self.num_frame+1
		# 帧数列
		worksheet.write(row, 0, self.num_frame+1)
		# 路人数目列
		worksheet.write(row, 2, count_obj['person'])
		# 汽车数目列
		worksheet.write(row, 4, count_obj['car'])
		# 摩托车数目列
		worksheet.write(row, 6, count_obj['motorbike'])
		# 车流量统计列
		worksheet.write(row, 8, self.traffic_sta)

		if self.IfLicensePlateRecognition:
			license_text = ""
			for license in self.license_plate:
				license_text += (license+',')
			license_text = license_text[0:len(license_text)-1]
			worksheet.write(row, 12, license_text)



