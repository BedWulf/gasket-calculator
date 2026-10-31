"""Визуальное редактирование контура прокладки в мм.

Вершины перетаскиваются мышью; координаты можно указать с точностью 0.01 мм.
Размерные подписи справочные. Геометрия проверяется до принятия изменений.
"""
from __future__ import annotations

from copy import deepcopy
from math import cos, sin, pi, hypot

from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt6.QtGui import QColor, QBrush, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from algorithms.nesting import Part
from algorithms.contour_ops import fillet_corner

MAX_HANDLES = 350


def _qspin(value=0.0, minvalue=-1_000_000, maxvalue=1_000_000):
    w=QDoubleSpinBox();w.setRange(minvalue,maxvalue);w.setDecimals(2)
    w.setValue(value);w.setSingleStep(1);w.setSuffix(' мм')
    return w


class GridScene(QGraphicsScene):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor=editor

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor('#fcfcfd'))
        step=self.editor.grid.value()
        if not self.editor.snap.isChecked() or step <= 0:
            return
        # Ограничить число линий при сильном уменьшении масштаба.
        left=int(rect.left()//step);right=int(rect.right()//step)
        top=int(rect.top()//step);bottom=int(rect.bottom()//step)
        if (right-left)+(bottom-top)>600: return
        pen=QPen(QColor('#e6ebef'),0)
        painter.setPen(pen)
        for x in range(left,right+1):
            xx=x*step;painter.drawLine(QPointF(xx,rect.top()),QPointF(xx,rect.bottom()))
        for y in range(top,bottom+1):
            yy=y*step;painter.drawLine(QPointF(rect.left(),yy),QPointF(rect.right(),yy))


class VertexHandle(QGraphicsEllipseItem):
    def __init__(self, editor, ring_idx, point_idx, pos):
        super().__init__(-4,-4,8,8)
        self.editor=editor;self.ring_idx=ring_idx;self.point_idx=point_idx
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
                      QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setBrush(QBrush(QColor('#ef8f3e') if ring_idx else QColor('#1976b9')))
        self.setPen(QPen(QColor('#ffffff'),1))
        self.setZValue(10)
        self.setPos(QPointF(*pos))
        self.setToolTip(f'Вершина {point_idx+1} · {pos[0]:.2f}; {pos[1]:.2f} мм')

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.editor._snapshot()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.editor.ready:
            QTimer.singleShot(0, self.editor._draw_all)

    def itemChange(self,change,value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.editor.ready:
            p=QPointF(value)
            if self.editor.snap.isChecked():
                grid=self.editor.grid.value()
                p=QPointF(round(p.x()/grid)*grid,round(p.y()/grid)*grid)
            return p
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.editor.ready:
            self.editor.vertex_moved(self.ring_idx,self.point_idx,self.pos())
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and self.editor.ready and value:
            self.editor.vertex_selected(self.ring_idx,self.point_idx)
        return super().itemChange(change,value)


class ContourView(QGraphicsView):
    def mouseDoubleClickEvent(self,event):
        self.scene().editor._double_click(event)

    def wheelEvent(self,event):
        factor=1.12 if event.angleDelta().y()>0 else 1/1.12
        self.scale(factor,factor)


class ContourEditor(QDialog):
    def __init__(self, points, holes=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Редактор контура — размеры в мм')
        self.resize(1050,750)
        self.rings=[deepcopy(points),*deepcopy(holes or [])]
        if not self.rings[0]: self.rings[0]=[(0,0),(150,0),(150,100),(0,100)]
        self.undo_stack=[]
        self.ready=False
        self.handles=[]
        self.annotations=[]
        self.path_item=None
        self._build()
        self._draw_all(fit=True)
        self.ready=True

    def _build(self):
        root=QVBoxLayout(self)
        helptext=QLabel('Синие точки — внешний контур, оранжевые — отверстия. Перетащите вершину либо введите координаты справа. '
                        'Двойной клик по фигуре добавляет вершину в ближайшее ребро выбранного контура. '
                        'Все размеры — мм; размерные линии справочные.')
        helptext.setWordWrap(True);root.addWidget(helptext)
        body=QHBoxLayout();root.addLayout(body,stretch=1)
        self.scene=GridScene(self)
        self.view=ContourView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setMinimumWidth(600)
        body.addWidget(self.view,stretch=1)
        side=QVBoxLayout();body.addLayout(side)
        form=QFormLayout()
        self.active_ring=QComboBox();self.active_ring.currentIndexChanged.connect(self._sync_fields)
        self.active_vertex=QSpinBox();self.active_vertex.setRange(1,50000);self.active_vertex.valueChanged.connect(self._sync_coords)
        self.x=_qspin();self.y=_qspin()
        form.addRow('Контур:',self.active_ring)
        form.addRow('Вершина №:',self.active_vertex)
        form.addRow('X:',self.x);form.addRow('Y:',self.y)
        side.addLayout(form)
        move=QPushButton('Применить координаты')
        move.clicked.connect(self.apply_coordinates);side.addWidget(move)
        row=QHBoxLayout();side.addLayout(row)
        for label,slot in (('＋ Вершина',self.add_vertex),('− Вершина',self.remove_vertex)):
            b=QPushButton(label);b.clicked.connect(slot);row.addWidget(b)
        for label,slot in (('Скруглить выбранный угол (R)',self.fillet_selected),
                           ('＋ Прямоугольное отверстие',self.add_rect_hole),
                           ('＋ Круглое отверстие',self.add_round_hole),
                           ('Удалить отверстие',self.delete_hole),('↶ Отменить изменение',self.undo)):
            b=QPushButton(label);b.clicked.connect(slot);side.addWidget(b)
        self.snap=QCheckBox('Привязка к сетке');self.snap.setChecked(False)
        self.snap.toggled.connect(lambda _:self.scene.update())
        self.grid=_qspin(5,0.01,1000);self.grid.valueChanged.connect(lambda _:self.scene.update())
        side.addWidget(self.snap)
        grid_form=QFormLayout();grid_form.addRow('Шаг сетки:',self.grid);side.addLayout(grid_form)
        self.info=QLabel();self.info.setWordWrap(True);side.addWidget(self.info)
        side.addStretch(1)
        fit=QPushButton('Показать контур целиком');fit.clicked.connect(self.fit);side.addWidget(fit)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _snapshot(self):
        self.undo_stack.append(deepcopy(self.rings))
        if len(self.undo_stack)>50:self.undo_stack.pop(0)

    def _polygon_check(self):
        p=Part('Деталь','polygon',points=self.rings[0],holes=self.rings[1:]);p.check()
        return p

    def _draw_all(self,fit=False):
        self.ready=False
        self.scene.clear();self.handles=[];self.annotations=[]
        path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
        for ring in self.rings:
            if not ring:continue
            path.moveTo(QPointF(*ring[0]))
            for pt in ring[1:]:path.lineTo(QPointF(*pt))
            path.closeSubpath()
        fill=QGraphicsPathItem(path)
        fill.setBrush(QBrush(QColor(94,165,206,105)))
        fill.setPen(QPen(QColor('#26475d'),0.55))
        fill.setZValue(-1)
        self.scene.addItem(fill);self.path_item=fill
        count=sum(map(len,self.rings))
        if count<=MAX_HANDLES:
            for ring_id,ring in enumerate(self.rings):
                for point_id,pt in enumerate(ring):
                    h=VertexHandle(self,ring_id,point_id,pt)
                    self.scene.addItem(h);self.handles.append(h)
        self._annotations()
        selected_ring=self.active_ring.currentIndex()
        self.active_ring.blockSignals(True);self.active_ring.clear()
        for idx in range(len(self.rings)):
            self.active_ring.addItem('Внешний контур' if idx==0 else f'Отверстие {idx}',idx)
        self.active_ring.setCurrentIndex(max(0,min(selected_ring,len(self.rings)-1)))
        self.active_ring.blockSignals(False)
        self._sync_fields()
        self.ready=True
        if fit:self.fit()
        try:
            p=self._polygon_check()
            self.info.setText(f'Габариты: {p.geometry().bounds[2]:.2f} × {p.geometry().bounds[3]:.2f} мм\n'
                              f'Площадь: {p.actual_area():.2f} мм²\n'
                              + ('Слишком много вершин для перетаскивания — используйте точные координаты.' if count>MAX_HANDLES else 'Контур корректен.'))
        except ValueError as exc:self.info.setText('⚠ Контур требует исправления: '+str(exc))

    def _annotations(self):
        if not self.rings or not self.rings[0]:return
        outer=self.rings[0]
        xmin=min(p[0] for p in outer);xmax=max(p[0] for p in outer)
        ymin=min(p[1] for p in outer);ymax=max(p[1] for p in outer)
        def label(text,x,y,color='#435463'):
            t=self.scene.addSimpleText(text)
            t.setBrush(QBrush(QColor(color)))
            t.setPos(x,y);t.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            t.setZValue(11);return t
        label(f'{xmax-xmin:.2f} мм',xmin+(xmax-xmin)/2,ymax+12)
        label(f'{ymax-ymin:.2f} мм',xmax+12,ymin+(ymax-ymin)/2)
        pen=QPen(QColor('#a06a3c'),0.25,Qt.PenStyle.DashLine)
        self.scene.addLine(xmin,ymax+10,xmax,ymax+10,pen)
        self.scene.addLine(xmax+10,ymin,xmax+10,ymax,pen)
        if len(outer)<=25:
            for a,b in zip(outer,outer[1:]+outer[:1]):
                length=hypot(b[0]-a[0],b[1]-a[1])
                if length>8:
                    label(f'{length:.1f}',(a[0]+b[0])/2,(a[1]+b[1])/2,'#697782')

    def fit(self):
        bounds=self.scene.itemsBoundingRect().adjusted(-30,-30,30,30)
        if bounds.width()<1 or bounds.height()<1:return
        self.view.fitInView(bounds,Qt.AspectRatioMode.KeepAspectRatio)

    def _sync_fields(self,*_):
        ring=self.active_ring.currentIndex()
        if ring<0:return
        self.active_vertex.blockSignals(True)
        self.active_vertex.setMaximum(max(1,len(self.rings[ring])))
        self.active_vertex.setValue(1)
        self.active_vertex.blockSignals(False)
        self._sync_coords()

    def _sync_coords(self,*_):
        idx=self.active_ring.currentIndex();vertex=self.active_vertex.value()-1
        if idx<0 or vertex>=len(self.rings[idx]):return
        self.x.setValue(self.rings[idx][vertex][0]);self.y.setValue(self.rings[idx][vertex][1])

    def vertex_selected(self,ring_idx,vertex_idx):
        self.active_ring.setCurrentIndex(ring_idx)
        self.active_vertex.setValue(vertex_idx+1)

    def vertex_moved(self,ring_idx,point_idx,pos):
        self.rings[ring_idx][point_idx]=(round(pos.x(),3),round(pos.y(),3))
        self._sync_coords()
        # Keep items while dragging; rebuild only path and annotations.
        path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
        for ring in self.rings:
            path.moveTo(QPointF(*ring[0]))
            for pt in ring[1:]:path.lineTo(QPointF(*pt))
            path.closeSubpath()
        self.path_item.setPath(path)

    def apply_coordinates(self):
        ring_id=self.active_ring.currentIndex();vertex=self.active_vertex.value()-1
        if ring_id<0:return
        self._snapshot()
        self.rings[ring_id][vertex]=(self.x.value(),self.y.value())
        self._draw_all()

    def add_vertex(self):
        ring_id=self.active_ring.currentIndex();idx=self.active_vertex.value()-1
        if ring_id<0:return
        points=self.rings[ring_id];a=points[idx];b=points[(idx+1)%len(points)]
        self._snapshot();points.insert(idx+1,((a[0]+b[0])/2,(a[1]+b[1])/2))
        self._draw_all();self.active_ring.setCurrentIndex(ring_id);self.active_vertex.setValue(idx+2)

    def fillet_selected(self):
        ring_id=self.active_ring.currentIndex();idx=self.active_vertex.value()-1
        if ring_id<0:return
        from PyQt6.QtWidgets import QInputDialog
        radius,ok=QInputDialog.getDouble(self,'Скругление','Радиус R, мм:',5.0,0.01,100000,2)
        if not ok:return
        try:
            updated=fillet_corner(self.rings[ring_id],idx,radius)
            candidate=deepcopy(self.rings);candidate[ring_id]=updated
            Part('Тест','polygon',points=candidate[0],holes=candidate[1:]).check()
        except ValueError as exc:
            QMessageBox.warning(self,'Не удалось скруглить',str(exc));return
        self._snapshot();self.rings=candidate
        self._draw_all()

    def remove_vertex(self):
        ring_id=self.active_ring.currentIndex();idx=self.active_vertex.value()-1
        if ring_id<0 or len(self.rings[ring_id])<=3:
            QMessageBox.information(self,'Вершины','В замкнутом контуре минимум три вершины')
            return
        self._snapshot();del self.rings[ring_id][idx];self._draw_all()

    def _hole_dialog(self,round_hole):
        d=QDialog(self);d.setWindowTitle('Круглое отверстие' if round_hole else 'Прямоугольное отверстие')
        layout=QVBoxLayout(d);form=QFormLayout();layout.addLayout(form)
        cx=_qspin(30);cy=_qspin(30);form.addRow('X левого края/центра:',cx);form.addRow('Y левого края/центра:',cy)
        w=_qspin(15,0.01);form.addRow('Радиус:' if round_hole else 'Ширина:',w)
        h=None
        if not round_hole:
            h=_qspin(15,0.01);form.addRow('Высота:',h)
        btn=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        btn.accepted.connect(d.accept);btn.rejected.connect(d.reject);layout.addWidget(btn)
        if d.exec()!=QDialog.DialogCode.Accepted:return None
        x,y=cx.value(),cy.value()
        if round_hole:
            return [(x+w.value()*cos(2*pi*i/72),y+w.value()*sin(2*pi*i/72)) for i in range(72)]
        return [(x,y),(x+w.value(),y),(x+w.value(),y+h.value()),(x,y+h.value())]

    def _add_hole(self,round_hole):
        hole=self._hole_dialog(round_hole)
        if hole is None:return
        self._snapshot();self.rings.append(hole)
        try:self._polygon_check()
        except ValueError as e:
            self.rings=self.undo_stack.pop()
            QMessageBox.warning(self,'Отверстие не помещается',str(e));return
        self._draw_all();self.active_ring.setCurrentIndex(len(self.rings)-1)

    def add_rect_hole(self):self._add_hole(False)
    def add_round_hole(self):self._add_hole(True)

    def delete_hole(self):
        idx=self.active_ring.currentIndex()
        if idx<=0:return
        self._snapshot();del self.rings[idx];self._draw_all()

    def _double_click(self,event):
        ring_id=self.active_ring.currentIndex()
        if ring_id<0:return
        at=self.view.mapToScene(event.pos())
        pt=(at.x(),at.y());ring=self.rings[ring_id]
        closest=None
        for idx,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
            dx=b[0]-a[0];dy=b[1]-a[1]
            length2=dx*dx+dy*dy
            if length2<1e-12:continue
            t=max(0,min(1,((pt[0]-a[0])*dx+(pt[1]-a[1])*dy)/length2))
            x=a[0]+dx*t;y=a[1]+dy*t
            d=hypot(pt[0]-x,pt[1]-y)
            if closest is None or d<closest[0]:closest=(d,idx,x,y)
        if closest is not None:
            _,idx,x,y=closest
            self._snapshot();ring.insert(idx+1,(round(x,2),round(y,2)))
            self._draw_all();self.active_ring.setCurrentIndex(ring_id);self.active_vertex.setValue(idx+2)

    def undo(self):
        if self.undo_stack:
            self.rings=self.undo_stack.pop();self._draw_all()

    def accept_if_valid(self):
        try:self._polygon_check()
        except ValueError as exc:
            QMessageBox.warning(self,'Проверьте геометрию',str(exc));return
        self.accept()

    def get_geometry(self):return deepcopy(self.rings[0]),deepcopy(self.rings[1:])
