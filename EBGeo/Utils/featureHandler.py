# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2018-05-01
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Philipe Borba - Cartographic Engineer @ Brazilian Army
        email                : borba.philipe@eb.mil.br
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import absolute_import
from builtins import range
import itertools
import sys
import os
from qgis.core import (
    QgsMessageLog,
    QgsVectorLayer,
    QgsGeometry,
    QgsField,
    QgsVectorDataProvider,
    QgsFeatureRequest,
    QgsExpression,
    QgsFeature,
    QgsSpatialIndex,
    Qgis,
    QgsCoordinateTransform,
    QgsWkbTypes,
    QgsProcessingMultiStepFeedback,
    QgsVectorLayerUtils,
    QgsCoordinateReferenceSystem,
    QgsProject,
)
from qgis.PyQt.Qt import QObject, QVariant

from ..Utils.map_index import UtmGrid
import concurrent.futures

class FeatureHandler(QObject):
    def __init__(self, iface=None, parent=None):
        super(FeatureHandler, self).__init__()
        self.parent = parent
        self.iface = iface
        if iface:
            self.canvas = iface.mapCanvas()
        self.utmGrid = UtmGrid()
        self.stepsTotal = 0

    def getNewGridFeat(self, index, geom):
        feat = QgsFeature()
        geom.removeDuplicateNodes()
        geom = geom.snappedToGrid(0.000001, 0.000001)
        feat.setGeometry(geom)
        return feat

    def getSystematicGridFeatures(
        self,
        featureList,
        index,
        stopScale,
        coordinateTransformer,
        xSubdivisions=3,
        ySubdivisions=3,
        constraintDict=None,
        feedback=None,
    ):
        if feedback is not None and feedback.isCanceled():
            return
        scale = self.utmGrid.getScale(index)
        if scale == stopScale:
            frameGeom = self.createGridItem(
                index,
                coordinateTransformer,
                constraintDict,
                xSubdivisions=xSubdivisions,
                ySubdivisions=ySubdivisions,
            )
            if frameGeom is None:
                return
            newFeat = self.getNewGridFeat(index, frameGeom)
            featureList.append(newFeat)
        else:
            scaleId = self.utmGrid.getScaleIdFromiNomen(index)
            sufixIterator = list(
                itertools.chain.from_iterable(
                    self.utmGrid.scaleText[scaleId + 1]
                )  # flatten list into one single list
            )
            # localMultiStepFeedback = QgsProcessingMultiStepFeedback(
            #     len(sufixIterator),
            #     feedback
            # )
            for i, line in enumerate(sufixIterator):
                if feedback is not None and feedback.isCanceled():
                    break
                # localMultiStepFeedback.setCurrentStep(i)
                inomen2 = "{oldInomem}-{newPart}".format(oldInomem=index, newPart=line)
                if (
                    constraintDict is not None
                    and self.createGridItem(
                        inomen2,
                        coordinateTransformer,
                        constraintDict,
                        xSubdivisions=xSubdivisions,
                        ySubdivisions=ySubdivisions,
                    )
                    is None
                ):
                    continue
                self.getSystematicGridFeatures(
                    featureList,
                    inomen2,
                    stopScale,
                    coordinateTransformer,
                    xSubdivisions=xSubdivisions,
                    ySubdivisions=ySubdivisions,
                    constraintDict=constraintDict,
                    feedback=feedback,
                )

    def createGridItem(
        self,
        index,
        coordinateTransformer,
        constraintDict,
        xSubdivisions=3,
        ySubdivisions=3,
    ):
        frameGeom = self.utmGrid.getQgsPolygonFrame(
            index, xSubdivisions=xSubdivisions, ySubdivisions=ySubdivisions
        )
        frameGeom.transform(coordinateTransformer)
        if constraintDict is None:
            return frameGeom
        frameBB = frameGeom.boundingBox()
        engine = QgsGeometry.createGeometryEngine(frameGeom.constGet())
        engine.prepareGeometry()
        for fid in constraintDict["spatialIdx"].intersects(frameBB):
            if getattr(engine, constraintDict["predicate"])(
                constraintDict["idDict"][fid].geometry().constGet()
            ):
                return frameGeom
        return None

    def getSystematicGridFeaturesWithConstraint(
        self,
        featureList,
        inputLyr,
        stopScale,
        coordinateTransformer,
        xSubdivisions=3,
        ySubdivisions=3,
        feedback=None,
        predicate=None,
    ):
        """
        TODO: Progress
        """
        """if feedback is not None and feedback.isCanceled():
            return"""
        predicate = "intersects" if predicate is None else predicate
        multiStepFeedback = QgsProcessingMultiStepFeedback(2, feedback)
        multiStepFeedback.setCurrentStep(0)
        multiStepFeedback.pushInfo(self.tr("Creating spatial index"))
        spatialIdx, idDict = self.buildSpatialIndexAndIdDict(
            inputLyr, feedback=multiStepFeedback
        )
        multiStepFeedback.pushInfo(self.tr("Getting candidate start indexes"))
        xmin, ymin, xmax, ymax = self.getLyrUnprojectedGeographicBounds(inputLyr)
        inomenList = self.utmGrid.get_INOM_range_from_BB(xmin, ymin, xmax, ymax)
        multiStepFeedback.setCurrentStep(1)
        multiStepFeedback.pushInfo(self.tr("Building grid"))
        gridMultistepFeedback = QgsProcessingMultiStepFeedback(
            len(inomenList), multiStepFeedback
        )
        constraintDict = {
            "spatialIdx": spatialIdx,
            "idDict": idDict,
            "predicate": predicate,
        }
        sys.setrecursionlimit(10**7)

        def compute(x):
            self.getSystematicGridFeatures(
                featureList,
                x,
                stopScale,
                coordinateTransformer,
                xSubdivisions=xSubdivisions,
                ySubdivisions=ySubdivisions,
                constraintDict=constraintDict,
                feedback=gridMultistepFeedback,
            )

        pool = concurrent.futures.ThreadPoolExecutor(os.cpu_count())
        futures = []
        current_idx = 0
        for inomen in inomenList:
            # gridMultistepFeedback.setCurrentStep(i)
            if gridMultistepFeedback.isCanceled():
                break
            futures.append(pool.submit(compute, inomen))

        for x in concurrent.futures.as_completed(futures):
            if gridMultistepFeedback.isCanceled():
                break
            gridMultistepFeedback.setCurrentStep(current_idx)
            current_idx += 1

    def buildSpatialIndexAndIdDict(self, inputLyr, feedback=None, featureRequest=None):
        """
        creates a spatial index for the input layer
        :param inputLyr: (QgsVectorLayer) input layer;
        :param feedback: (QgsProcessingFeedback) processing feedback;
        :param featureRequest: (QgsFeatureRequest) optional feature request;
        """
        spatialIdx = QgsSpatialIndex()
        idDict = {}
        featCount = inputLyr.featureCount()
        size = 100 / featCount if featCount else 0
        iterator = (
            inputLyr.getFeatures()
            if featureRequest is None
            else inputLyr.getFeatures(featureRequest)
        )

        def addFeatureAlias(x):
            return self.addFeatureToSpatialIndex(
                current=x[0],
                feat=x[1],
                spatialIdx=spatialIdx,
                idDict=idDict,
                size=size,
                feedback=feedback,
            )

        list(map(addFeatureAlias, enumerate(iterator)))
        return spatialIdx, idDict

    def addFeatureToSpatialIndex(
        self, current, feat, spatialIdx, idDict, size, feedback
    ):
        """
        Adds feature to spatial index. Used along side with a
        python map operator to improve performance.
        :param current : (int) current index
        :param feat : (QgsFeature) feature to be added on spatial
        index and on idDict
        :param spatialIdx: (QgsSpatialIndex) spatial index
        :param idDict: (dict) dictionary with format {feat.id(): feat}
        :param size: (int) size to be used to update feedback
        :param feedback: (QgsProcessingFeedback) feedback to be used
        on processing
        """
        if feedback is not None and feedback.isCanceled():
            return
        idDict[feat.id()] = feat
        spatialIdx.addFeature(feat)
        if feedback is not None:
            feedback.setProgress(size * current)

    def getLyrUnprojectedGeographicBounds(self, inputLyr):
        crs = inputLyr.crs()
        coordinateTransformer = QgsCoordinateTransform(
            crs,
            QgsCoordinateReferenceSystem(crs.geographicCrsAuthId()),
            QgsProject.instance(),
        )
        reprojectedGeographicBB = coordinateTransformer.transformBoundingBox(
            inputLyr.extent()
        )
        xmin = reprojectedGeographicBB.xMinimum()
        ymin = reprojectedGeographicBB.yMinimum()
        xmax = reprojectedGeographicBB.xMaximum()
        ymax = reprojectedGeographicBB.yMaximum()
        return xmin, xmax, ymin, ymax
