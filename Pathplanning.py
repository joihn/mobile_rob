import numpy as np
from importlib import reload
import matplotlib.pyplot as plt
from extremitypathfinder.extremitypathfinder import PolygonEnvironment as Environment

from shapely.geometry import Polygon
from shapely.ops import cascaded_union

import vision
import cv2

class Obstacle:
    def __init__(self, vertexList, margeObs):
        self.vertex=vertexList
        self.polygone= Polygon(vertexList)
        self.polygoneExpanded = self.polygone.buffer(margeObs, resolution=2)
        self.expandEnabled=True
        self.computeExpandedVertices()

    def computeExpandedVertices(self):
        coordList= list(zip( self.polygoneExpanded.exterior.coords.xy[0], self.polygoneExpanded.exterior.coords.xy[1]))
        self.vertexExpanded = coordList[:-1] #delete last vertice to avoid re-looping

MAP_MAX_X_AXIS= 81
MAP_MAX_Y_AXIS= 114

def take_picture_to_init(margeObs=5, cam_capture=2):
    """
    will take a picture from webcam and recognise the different element of the map,
    will return the different obstacle as polygons (already expanded to void thymio colision,
    Polygons are here described as set of vertices in clockwise order

    librairie used for polygon manipulation: Shapely
    https://shapely.readthedocs.io/en/stable/manual.html

    Tutorial to merge 2 polygons:
    https://deparkes.co.uk/2015/02/28/how-to-merge-polygons-in-python/

    """
    Environment = reload(extremitypathfinder.extremitypathfinder.PolygonEnvironment)
    img, vision_img = vision.capture_image_from_webcam(cam_capture)

    pix_to_unit_x = 27*3/img.shape[1]
    pix_to_unit_y = 38*3/img.shape[0]

    thymioCoord = vision.detect_thymio(img)
    if thymioCoord is None:
        print("thymio not found")
    goal = vision.detect_goal(img)
    if goal is not None:
        goal = (goal[0]*pix_to_unit_x, goal[1]*pix_to_unit_y)
    else:
        print("goal not found")
    obstacles_vision = vision.detect_obstacles(img)

    obsList = []
    for obst_vis in obstacles_vision:
        obst_vis = obst_vis.astype('float64')
        obst_vis[:, :, 0] *= pix_to_unit_x
        obst_vis[:, :, 1] *= pix_to_unit_y
        vertex_vision = np.ndarray.tolist(obst_vis.squeeze())
        obsList.append(Obstacle(vertex_vision, margeObs))  # converting obstacle to correct format

    # Merging the coliding obstacle
    for i in range(0, len(obsList)):
        for j in range(0, len(obsList) ):
            if i!=j and obsList[i].expandEnabled and obsList[j].expandEnabled and \
                    obsList[i].polygoneExpanded.intersects(obsList[j].polygoneExpanded):
                obsList[i].polygoneExpanded=cascaded_union([obsList[i].polygoneExpanded, obsList[j].polygoneExpanded])
                obsList[i].computeExpandedVertices()
                obsList[j].expandEnabled = False

    return thymioCoord[0]*pix_to_unit_x, thymioCoord[1]*pix_to_unit_y, thymioCoord[2], goal, obsList, vision_img


def find_path(thymioCoord, goal, obsListOrig, plotFlag=True):
    """Given an inital position, a goal and a set of obstacle, will create a Visibility Graph of the map,
    then perform an A* search on the given graph, and return the shortest path
    Librairy used for visiblity Graph generation and Graph search:https://github.com/MrMinimal64/extremitypathfinder
    """

    obsList=obsListOrig.copy()
    MARGE_BORD=5
    EXTREME_DIST=400
    # if obstacle are near the map border, make them bigger so we are surefound path dosn't go trough the small gap
    for iObs in range(0, len(obsList)):
        for iVert in range(0, len(obsList[iObs].vertexExpanded)):
            listV=list(obsList[iObs].vertexExpanded[iVert])
            if listV[0]>MAP_MAX_X_AXIS-MARGE_BORD:
                listV[0] = EXTREME_DIST
                obsList[iObs].vertexExpanded[iVert]=listV
            if listV[0]<0+MARGE_BORD:
                listV[0] = -EXTREME_DIST
                obsList[iObs].vertexExpanded[iVert]=listV
            if listV[1]>MAP_MAX_Y_AXIS-MARGE_BORD:
                listV[1]= EXTREME_DIST
                obsList[iObs].vertexExpanded[iVert] = listV
            if listV[1]<0+MARGE_BORD:
                listV[1]= -EXTREME_DIST
                obsList[iObs].vertexExpanded[iVert] = listV

    if plotFlag:
        for obs in obsList:
            unzippedList = list(zip(*obs.vertex))
            unzippedList = [list(elem) for elem in unzippedList]
            unzippedList[0].append(unzippedList[0][0])
            unzippedList[1].append(unzippedList[1][0])
            plt.plot(unzippedList[0], unzippedList[1])
            if obs.expandEnabled:
                unzippedList=list(zip(*obs.vertexExpanded))
                unzippedList = [list(elem) for elem in unzippedList]
                unzippedList[0].append(unzippedList[0][0])
                unzippedList[1].append(unzippedList[1][0])
                plt.plot(unzippedList[0], unzippedList[1], '--')
        plt.plot(thymioCoord[0], thymioCoord[1], 'o', color='green')
        plt.plot(goal[0], goal[1], 'o', color='red')

    map = Environment()

    # boundary of the map, anti clockwise vertex numbering!
    boundary_coordinates = [(0.0, 0.0), (MAP_MAX_X_AXIS, 0.0), (MAP_MAX_X_AXIS, MAP_MAX_Y_AXIS), (0.0, MAP_MAX_Y_AXIS)]


    list_of_obstacle = []
    for obs in obsList:
        if obs.expandEnabled:
            list_of_obstacle.append(obs.vertexExpanded)

    map.store(boundary_coordinates, list_of_obstacle, validate=False)
    map.prepare()
    path, length = map.find_shortest_path(thymioCoord, goal)
    if plotFlag:
        unzippedPath = list(zip(*path))
        plt.plot(unzippedPath[0], unzippedPath[1], '--', color='black')
        plt.xlim(0, MAP_MAX_X_AXIS)
        plt.ylim(0, MAP_MAX_Y_AXIS)
        plt.gca().set_aspect('equal', adjustable='box')
        plt.show()
    return path


if __name__ == "__main__":
#     # [thymioCoord, thymioTh, goal, obsList]=take_picture_to_init(margeObs=5, cam_capture=2)
     dx=-55
     thymioCoord=[1, 20]
     goal = [1, 50]
     obs1=Obstacle([(60+dx,35),(80+dx,35),(80+dx,30),(60+dx,30)], 1)
     find_path(thymioCoord, goal, [obs1], plotFlag=True)
     find_path(thymioCoord, goal, [obs1], plotFlag=True)
     find_path(thymioCoord, goal, [obs1], plotFlag=True)
     find_path(thymioCoord, goal, [obs1], plotFlag=True)
     find_path(thymioCoord, goal, [obs1], plotFlag=True)