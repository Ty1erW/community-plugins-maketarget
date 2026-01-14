#!/usr/bin/python
# -*- coding: utf-8 -*-

import bpy, bpy_extras, os, re
from bpy_extras.io_utils import ImportHelper
from .maketarget2 import calculateScaleFactor
from bpy.props import BoolProperty, StringProperty, EnumProperty, IntProperty, CollectionProperty, FloatProperty

class MHC_OT_LoadTargetOperator(bpy.types.Operator, ImportHelper):
    """Load required shape keys from file (i.e load a target)"""
    bl_idname = "mh_community.load_target"
    bl_label = "Load target(s)"
    
    # 添加 files 属性来支持多文件选择
    files : CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    
    # 修改 filter_glob 以支持多选
    filter_glob : StringProperty(default='*.target', options={'HIDDEN'})
    
    # 添加目录属性，用于存储多选时的目录路径
    directory : StringProperty(maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object")
            return {'CANCELLED'}
        
        # 检查是否有多文件
        if not self.files:
            # 单个文件模式（向后兼容）
            return self._load_single_target(context, self.filepath)
        else:
            # 多文件模式
            return self._load_multiple_targets(context)

    def _load_single_target(self, context, filepath):
        """加载单个target文件"""
        filename, extension = os.path.splitext(filepath)
        target = os.path.basename(filename)

        obj = context.active_object
        obj.MhNewTargetName = target

        if not obj.data.shape_keys:
            basis = obj.shape_key_add(name="Basis", from_mix=False)
        nextTarget = obj.shape_key_add(name=target, from_mix=False)
        # 修改：默认值设为0，而不是1
        nextTarget.value = 0.0  

        idx = obj.data.shape_keys.key_blocks.find(target)
        context.active_object.active_shape_key_index = idx

        sks = obj.data.shape_keys
        pt = sks.key_blocks[target]
        mx = len(pt.data)

        scaleFactor = calculateScaleFactor(bpy.context.scene, None)

        with open(filepath,'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = re.compile(r"\s+").split(line.strip())
                    index = int(parts[0])
                    x = float(parts[1]) * scaleFactor
                    z = float(parts[2]) * scaleFactor
                    y = -float(parts[3]) * scaleFactor

                    if index < mx:      # avoid target for helpers to get in conflict if only body is loaded
                        pt.data[index].co[0] = pt.data[index].co[0] + x
                        pt.data[index].co[1] = pt.data[index].co[1] + y
                        pt.data[index].co[2] = pt.data[index].co[2] + z

        self.report({'INFO'}, f"Target '{target}' loaded")
        return {'FINISHED'}

    def _load_multiple_targets(self, context):
        """加载多个target文件"""
        obj = context.active_object
        
        # 确保有基础形状键
        if not obj.data.shape_keys:
            obj.shape_key_add(name="Basis", from_mix=False)
        
        scaleFactor = calculateScaleFactor(bpy.context.scene, None)
        loaded_count = 0
        last_loaded_target = None
        
        # 遍历所有选中的文件
        for file_elem in self.files:
            filepath = os.path.join(self.directory, file_elem.name)
            
            # 检查文件是否存在
            if not os.path.exists(filepath):
                self.report({'WARNING'}, f"File not found: {filepath}")
                continue
            
            filename, extension = os.path.splitext(file_elem.name)
            target_name = filename
            
            # 检查是否已存在同名形状键
            if obj.data.shape_keys and target_name in obj.data.shape_keys.key_blocks:
                self.report({'WARNING'}, f"Shape key '{target_name}' already exists, skipping")
                continue
            
            # 创建新的形状键
            nextTarget = obj.shape_key_add(name=target_name, from_mix=False)
            # 修改：默认值设为0，而不是1
            nextTarget.value = 0.0  
            loaded_count += 1
            last_loaded_target = target_name
            
            # 获取形状键数据
            sks = obj.data.shape_keys
            pt = sks.key_blocks[target_name]
            mx = len(pt.data)
            
            # 读取文件并应用顶点偏移
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = re.compile(r"\s+").split(line.strip())
                            index = int(parts[0])
                            x = float(parts[1]) * scaleFactor
                            z = float(parts[2]) * scaleFactor
                            y = -float(parts[3]) * scaleFactor

                            if index < mx:  # 避免索引越界
                                pt.data[index].co[0] = pt.data[index].co[0] + x
                                pt.data[index].co[1] = pt.data[index].co[1] + y
                                pt.data[index].co[2] = pt.data[index].co[2] + z
            except Exception as e:
                self.report({'ERROR'}, f"Error loading {file_elem.name}: {str(e)}")
                # 删除创建失败的形状键
                if obj.data.shape_keys:
                    obj.shape_key_remove(pt)
                loaded_count -= 1
        
        # 设置最后一个加载的target为活动形态键
        if last_loaded_target and obj.data.shape_keys:
            idx = obj.data.shape_keys.key_blocks.find(last_loaded_target)
            if idx >= 0:
                obj.active_shape_key_index = idx
        
        # 报告结果
        if loaded_count > 0:
            self.report({'INFO'}, f"Successfully loaded {loaded_count} target(s)")
        else:
            self.report({'WARNING'}, "No targets were loaded")
        
        return {'FINISHED'}

    @classmethod
    def poll(self, context):
        if context.active_object is not None:
            obj = context.active_object
            if not hasattr(obj, "MhObjectType"):
                return False
            if obj.select_get():
                if obj.MhObjectType == "Basemesh" or obj.MhObjectType == "_CustomBase_":
                    return True
        return False