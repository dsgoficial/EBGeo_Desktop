# -*- coding: UTF-8 -*-
from qgis.core import *
import math

class AuxiliarDeclConv(object):
    
    def __init__(self, iface):
        super(AuxiliarDeclConv, self).__init__()
        self.iface = iface
        
    def calculateConvergence(self, point):
        """Calculates the meridian convergence
        """
        latitude = point.y()
        longitude = point.x()

        (a, b) = self.getSemiMajorAndSemiMinorAxis()
        
        centralMeridian = self.getCentralMeridian(longitude)

        deltaLong = abs( centralMeridian - longitude )

        p = 0.0001*( deltaLong*3600 )

        xii = math.sin(math.radians(latitude))*math.pow(10, 4)

        e2 = math.sqrt(a*a - b*b)/b

        c5 = math.pow(math.sin(math.radians(1/3600)), 4)*math.sin(math.radians(latitude))*math.pow(math.cos(math.radians(latitude)), 4)*(2 - math.pow(math.tan(math.radians(latitude)), 2))*math.pow(10, 20)/15

        xiii = math.pow(math.sin(math.radians(1/3600)), 2)*math.sin(math.radians(latitude))*math.pow(math.cos(math.radians(latitude)), 2)*(1 + 3*e2*e2*math.pow(math.cos(math.radians(latitude)), 2) + 2*math.pow(e2, 4)*math.pow(math.cos(math.radians(latitude)), 4))*math.pow(10, 12)/3

        cSeconds = xii*p + xiii*math.pow(p, 3) + c5*math.pow(p, 5)

        if longitude < centralMeridian:
            c = -cSeconds/3600
        else:
            c = cSeconds/3600

        return c

    def getSemiMajorAndSemiMinorAxis(self):
        """Obtains the semi major axis and semi minor axis from the used ellipsoid
        """
        distanceArea = QgsDistanceArea()
        distanceArea.setEllipsoid(self.iface.mapCanvas().mapSettings().destinationCrs().ellipsoidAcronym())
        a = distanceArea.ellipsoidSemiMajor()
        b = distanceArea.ellipsoidSemiMinor()
        
        return (a,b)
    
    def getCentralMeridian(self, longitude):
        centralMeridian = int(abs(longitude)/6)*6 + 3
        if longitude < 0:
            centralMeridian = centralMeridian*(-1)

        return centralMeridian
