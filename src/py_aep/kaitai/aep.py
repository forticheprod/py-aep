# This is a generated file! Please edit source .ksy file and use kaitai-struct-compiler to rebuild
# type: ignore

import kaitaistruct
from kaitaistruct import ReadWriteKaitaiStruct, KaitaiStream, BytesIO
from enum import IntEnum


if getattr(kaitaistruct, 'API_VERSION', (0, 9)) < (0, 11):
    raise Exception("Incompatible Kaitai Struct Python API: 0.11 or later is required, but you have %s" % (kaitaistruct.__version__))

class Aep(ReadWriteKaitaiStruct):

    class AssetType(IntEnum):
        placeholder = 2
        solid = 9

    class AutoOrientType(IntEnum):
        no_auto_orient = 0
        along_path = 1
        camera_or_point_of_interest = 2
        characters_toward_camera = 3

    class FastPreviewType(IntEnum):
        false = 0
        adaptive_resolution = 1
        draft = 2
        fast_draft = 3
        wireframe = 4

    class FrameBlendingType(IntEnum):
        no_frame_blend = 0
        frame_mix = 1
        pixel_motion = 2

    class ItemType(IntEnum):
        folder = 1
        composition = 4
        footage = 7

    class Label(IntEnum):
        none = 0
        red = 1
        yellow = 2
        aqua = 3
        pink = 4
        lavender = 5
        peach = 6
        sea_foam = 7
        blue = 8
        green = 9
        purple = 10
        orange = 11
        brown = 12
        fuchsia = 13
        cyan = 14
        sandstone = 15
        dark_green = 16

    class LayerType(IntEnum):
        avlayer = 0
        light = 1
        camera = 2
        text = 3
        shape = 4
        three_d_model = 5

    class LdatItemType(IntEnum):
        unknown = 0
        no_value = 1
        three_d_spatial = 2
        three_d = 3
        two_d_spatial = 4
        two_d = 5
        one_d = 6
        color = 7
        custom_value = 8
        marker = 9
        layer_index = 10
        mask_index = 11
        shape = 12
        text_document = 13
        lrdr = 14
        litm = 15
        gide = 16
        orientation = 17

    class PropertyControlType(IntEnum):
        layer = 0
        scalar = 2
        angle = 3
        boolean = 4
        color = 5
        two_d = 6
        enum = 7
        paint_group = 9
        slider = 10
        curve = 11
        group = 13
        unknown = 15
        three_d = 18
    def __init__(self, _io=None, _parent=None, _root=None):
        super(Aep, self).__init__(_io)
        self._parent = _parent
        self._root = _root or self

    def _read(self):
        self.root = Aep.Chunk(self._io, self, self._root)
        self.root._read()
        self.xmp_packet = (self._io.read_bytes_full()).decode(u"UTF-8")
        self._dirty = False


    def _fetch_instances(self):
        pass
        self.root._fetch_instances()


    def _write__seq(self, io=None):
        super(Aep, self)._write__seq(io)
        self.root._write__seq(self._io)
        self._io.write_bytes((self.xmp_packet).encode(u"UTF-8"))
        if not self._io.is_eof():
            raise kaitaistruct.ConsistencyError(u"xmp_packet", 0, self._io.size() - self._io.pos())


    def _check(self):
        if self.root._root != self._root:
            raise kaitaistruct.ConsistencyError(u"root", self._root, self.root._root)
        if self.root._parent != self:
            raise kaitaistruct.ConsistencyError(u"root", self, self.root._parent)
        self._dirty = False

    class AcerBody(ReadWriteKaitaiStruct):
        """Compensate for Scene-Referred Profiles setting in Project Settings.
        This setting affects how scene-referred color profiles are handled.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.AcerBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.compensate_for_scene_referred_profiles = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.AcerBody, self)._write__seq(io)
            self._io.write_u1(self.compensate_for_scene_referred_profiles)


        def _check(self):
            self._dirty = False


    class AdfrBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.AdfrBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.audio_sample_rate = self._io.read_f8be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.AdfrBody, self)._write__seq(io)
            self._io.write_f8be(self.audio_sample_rate)


        def _check(self):
            self._dirty = False


    class ApidBody(ReadWriteKaitaiStruct):
        """Media color space ICC Profile ID.
        Inside LIST:CLRS in a footage item's LIST:Pin.
        A 16-byte ICC Profile ID identifying the color space to assign
        to the footage. All 0xFF bytes means "Embedded" (use the
        media's native profile).
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.ApidBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.profile_id = self._io.read_bytes(16)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.ApidBody, self)._write__seq(io)
            self._io.write_bytes(self.profile_id)


        def _check(self):
            if len(self.profile_id) != 16:
                raise kaitaistruct.ConsistencyError(u"profile_id", 16, len(self.profile_id))
            self._dirty = False


    class AsciiBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.AsciiBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.contents = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.AsciiBody, self)._write__seq(io)
            self._io.write_bytes(self.contents)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"contents", 0, self._io.size() - self._io.pos())


        def _check(self):
            self._dirty = False


    class CdatBody(ReadWriteKaitaiStruct):
        """Property value chunk storing one or more doubles.
        When is_le is true (OTST orientation), values are little-endian.
        """
        def __init__(self, is_le, _io=None, _parent=None, _root=None):
            super(Aep.CdatBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.is_le = is_le

        def _read(self):
            if (not (self.is_le)):
                pass
                self.value_be = []
                for i in range(self._parent.len_body // 8):
                    self.value_be.append(self._io.read_f8be())


            if self.is_le:
                pass
                self.value_le = []
                for i in range(self._parent.len_body // 8):
                    self.value_le.append(self._io.read_f8le())


            self._dirty = False


        def _fetch_instances(self):
            pass
            if (not (self.is_le)):
                pass
                for i in range(len(self.value_be)):
                    pass


            if self.is_le:
                pass
                for i in range(len(self.value_le)):
                    pass




        def _write__seq(self, io=None):
            super(Aep.CdatBody, self)._write__seq(io)
            if (not (self.is_le)):
                pass
                for i in range(len(self.value_be)):
                    pass
                    self._io.write_f8be(self.value_be[i])


            if self.is_le:
                pass
                for i in range(len(self.value_le)):
                    pass
                    self._io.write_f8le(self.value_le[i])




        def _check(self):
            if (not (self.is_le)):
                pass
                if len(self.value_be) != self._parent.len_body // 8:
                    raise kaitaistruct.ConsistencyError(u"value_be", self._parent.len_body // 8, len(self.value_be))
                for i in range(len(self.value_be)):
                    pass


            if self.is_le:
                pass
                if len(self.value_le) != self._parent.len_body // 8:
                    raise kaitaistruct.ConsistencyError(u"value_le", self._parent.len_body // 8, len(self.value_le))
                for i in range(len(self.value_le)):
                    pass


            self._dirty = False

        @property
        def value(self):
            if hasattr(self, '_m_value'):
                return self._m_value

            self._m_value = (self.value_le if self.is_le else self.value_be)
            return getattr(self, '_m_value', None)

        def _invalidate_value(self):
            del self._m_value

    class CdrpBody(ReadWriteKaitaiStruct):
        """Composition drop frame setting.
        When true, the composition uses drop-frame timecode.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.CdrpBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.drop_frame = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.CdrpBody, self)._write__seq(io)
            self._io.write_u1(self.drop_frame)


        def _check(self):
            self._dirty = False


    class CdtaBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.CdtaBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.resolution_factor = []
            for i in range(2):
                self.resolution_factor.append(self._io.read_u2be())

            self._unnamed1 = self._io.read_bytes(1)
            self.time_scale_integer = self._io.read_u2be()
            self.time_scale_fractional = self._io.read_u1()
            self.internal_timebase = self._io.read_u4be()
            self._unnamed5 = self._io.read_bytes(4)
            self.standard_timebase = self._io.read_u4be()
            self.time_dividend = self._io.read_s4be()
            self.time_divisor = self._io.read_u4be()
            self.work_area_start_dividend = self._io.read_u4be()
            self.work_area_start_divisor = self._io.read_u4be()
            self.work_area_end_dividend = self._io.read_u4be()
            self.work_area_end_divisor = self._io.read_u4be()
            self.duration_dividend = self._io.read_u4be()
            self.duration_divisor = self._io.read_u4be()
            self.bg_color = []
            for i in range(3):
                self.bg_color.append(self._io.read_u1())

            self._unnamed16 = self._io.read_bytes(83)
            self.draft3d = self._io.read_bits_int_be(1) != 0
            self._unnamed18 = self._io.read_bits_int_be(7)
            self.preserve_nested_resolution = self._io.read_bits_int_be(1) != 0
            self._unnamed20 = self._io.read_bits_int_be(1) != 0
            self.preserve_nested_frame_rate = self._io.read_bits_int_be(1) != 0
            self.frame_blending = self._io.read_bits_int_be(1) != 0
            self.motion_blur = self._io.read_bits_int_be(1) != 0
            self._unnamed24 = self._io.read_bits_int_be(2)
            self.hide_shy_layers = self._io.read_bits_int_be(1) != 0
            self.width = self._io.read_u2be()
            self.height = self._io.read_u2be()
            self.pixel_ratio_dividend = self._io.read_u4be()
            self.pixel_ratio_divisor = self._io.read_u4be()
            self._unnamed30 = self._io.read_bytes(4)
            self.frame_rate_integer = self._io.read_u2be()
            self.frame_rate_fractional = self._io.read_u2be()
            self._unnamed33 = self._io.read_bytes(4)
            self.display_start_time_dividend = self._io.read_s4be()
            self.display_start_time_divisor = self._io.read_u4be()
            self._unnamed36 = self._io.read_bytes(2)
            self.shutter_angle = self._io.read_u2be()
            self._unnamed38 = self._io.read_bytes(4)
            self.shutter_phase = self._io.read_s4be()
            self._unnamed40 = self._io.read_bytes(4)
            self._unnamed41 = self._io.read_bytes(8)
            self.motion_blur_adaptive_sample_limit = self._io.read_s4be()
            self.motion_blur_samples_per_frame = self._io.read_s4be()
            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.resolution_factor)):
                pass

            for i in range(len(self.bg_color)):
                pass



        def _write__seq(self, io=None):
            super(Aep.CdtaBody, self)._write__seq(io)
            for i in range(len(self.resolution_factor)):
                pass
                self._io.write_u2be(self.resolution_factor[i])

            self._io.write_bytes(self._unnamed1)
            self._io.write_u2be(self.time_scale_integer)
            self._io.write_u1(self.time_scale_fractional)
            self._io.write_u4be(self.internal_timebase)
            self._io.write_bytes(self._unnamed5)
            self._io.write_u4be(self.standard_timebase)
            self._io.write_s4be(self.time_dividend)
            self._io.write_u4be(self.time_divisor)
            self._io.write_u4be(self.work_area_start_dividend)
            self._io.write_u4be(self.work_area_start_divisor)
            self._io.write_u4be(self.work_area_end_dividend)
            self._io.write_u4be(self.work_area_end_divisor)
            self._io.write_u4be(self.duration_dividend)
            self._io.write_u4be(self.duration_divisor)
            for i in range(len(self.bg_color)):
                pass
                self._io.write_u1(self.bg_color[i])

            self._io.write_bytes(self._unnamed16)
            self._io.write_bits_int_be(1, int(self.draft3d))
            self._io.write_bits_int_be(7, self._unnamed18)
            self._io.write_bits_int_be(1, int(self.preserve_nested_resolution))
            self._io.write_bits_int_be(1, int(self._unnamed20))
            self._io.write_bits_int_be(1, int(self.preserve_nested_frame_rate))
            self._io.write_bits_int_be(1, int(self.frame_blending))
            self._io.write_bits_int_be(1, int(self.motion_blur))
            self._io.write_bits_int_be(2, self._unnamed24)
            self._io.write_bits_int_be(1, int(self.hide_shy_layers))
            self._io.write_u2be(self.width)
            self._io.write_u2be(self.height)
            self._io.write_u4be(self.pixel_ratio_dividend)
            self._io.write_u4be(self.pixel_ratio_divisor)
            self._io.write_bytes(self._unnamed30)
            self._io.write_u2be(self.frame_rate_integer)
            self._io.write_u2be(self.frame_rate_fractional)
            self._io.write_bytes(self._unnamed33)
            self._io.write_s4be(self.display_start_time_dividend)
            self._io.write_u4be(self.display_start_time_divisor)
            self._io.write_bytes(self._unnamed36)
            self._io.write_u2be(self.shutter_angle)
            self._io.write_bytes(self._unnamed38)
            self._io.write_s4be(self.shutter_phase)
            self._io.write_bytes(self._unnamed40)
            self._io.write_bytes(self._unnamed41)
            self._io.write_s4be(self.motion_blur_adaptive_sample_limit)
            self._io.write_s4be(self.motion_blur_samples_per_frame)


        def _check(self):
            if len(self.resolution_factor) != 2:
                raise kaitaistruct.ConsistencyError(u"resolution_factor", 2, len(self.resolution_factor))
            for i in range(len(self.resolution_factor)):
                pass

            if len(self._unnamed1) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 1, len(self._unnamed1))
            if len(self._unnamed5) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed5", 4, len(self._unnamed5))
            if len(self.bg_color) != 3:
                raise kaitaistruct.ConsistencyError(u"bg_color", 3, len(self.bg_color))
            for i in range(len(self.bg_color)):
                pass

            if len(self._unnamed16) != 83:
                raise kaitaistruct.ConsistencyError(u"_unnamed16", 83, len(self._unnamed16))
            if len(self._unnamed30) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed30", 4, len(self._unnamed30))
            if len(self._unnamed33) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed33", 4, len(self._unnamed33))
            if len(self._unnamed36) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed36", 2, len(self._unnamed36))
            if len(self._unnamed38) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed38", 4, len(self._unnamed38))
            if len(self._unnamed40) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed40", 4, len(self._unnamed40))
            if len(self._unnamed41) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed41", 8, len(self._unnamed41))
            self._dirty = False

        @property
        def display_start_frame(self):
            if hasattr(self, '_m_display_start_frame'):
                return self._m_display_start_frame

            self._m_display_start_frame = self.display_start_time * self.frame_rate
            return getattr(self, '_m_display_start_frame', None)

        def _invalidate_display_start_frame(self):
            del self._m_display_start_frame
        @property
        def display_start_time(self):
            if hasattr(self, '_m_display_start_time'):
                return self._m_display_start_time

            self._m_display_start_time = (self.display_start_time_dividend * 1.0) / self.display_start_time_divisor
            return getattr(self, '_m_display_start_time', None)

        def _invalidate_display_start_time(self):
            del self._m_display_start_time
        @property
        def duration(self):
            if hasattr(self, '_m_duration'):
                return self._m_duration

            self._m_duration = (self.duration_dividend * 1.0) / self.duration_divisor
            return getattr(self, '_m_duration', None)

        def _invalidate_duration(self):
            del self._m_duration
        @property
        def frame_duration(self):
            if hasattr(self, '_m_frame_duration'):
                return self._m_frame_duration

            self._m_frame_duration = self.duration * self.frame_rate
            return getattr(self, '_m_frame_duration', None)

        def _invalidate_frame_duration(self):
            del self._m_frame_duration
        @property
        def frame_rate(self):
            if hasattr(self, '_m_frame_rate'):
                return self._m_frame_rate

            self._m_frame_rate = self.frame_rate_integer + (self.frame_rate_fractional * 1.0) / 65536
            return getattr(self, '_m_frame_rate', None)

        def _invalidate_frame_rate(self):
            del self._m_frame_rate
        @property
        def frame_time(self):
            if hasattr(self, '_m_frame_time'):
                return self._m_frame_time

            self._m_frame_time = self.time * self.frame_rate
            return getattr(self, '_m_frame_time', None)

        def _invalidate_frame_time(self):
            del self._m_frame_time
        @property
        def frame_work_area_duration(self):
            """Work area duration (frames)."""
            if hasattr(self, '_m_frame_work_area_duration'):
                return self._m_frame_work_area_duration

            self._m_frame_work_area_duration = self.frame_work_area_end_absolute - self.frame_work_area_start_absolute
            return getattr(self, '_m_frame_work_area_duration', None)

        def _invalidate_frame_work_area_duration(self):
            del self._m_frame_work_area_duration
        @property
        def frame_work_area_end_absolute(self):
            """Absolute work area end in composition time (frames). Internal."""
            if hasattr(self, '_m_frame_work_area_end_absolute'):
                return self._m_frame_work_area_end_absolute

            self._m_frame_work_area_end_absolute = (self.display_start_frame + self.frame_duration if self.work_area_end_dividend == 4294967295 else (self.display_start_time + (self.work_area_end_dividend * 1.0) / self.work_area_end_divisor) * self.frame_rate)
            return getattr(self, '_m_frame_work_area_end_absolute', None)

        def _invalidate_frame_work_area_end_absolute(self):
            del self._m_frame_work_area_end_absolute
        @property
        def frame_work_area_start_absolute(self):
            """Absolute work area start in composition time (frames). Internal."""
            if hasattr(self, '_m_frame_work_area_start_absolute'):
                return self._m_frame_work_area_start_absolute

            self._m_frame_work_area_start_absolute = (self.display_start_time + (self.work_area_start_dividend * 1.0) / self.work_area_start_divisor) * self.frame_rate
            return getattr(self, '_m_frame_work_area_start_absolute', None)

        def _invalidate_frame_work_area_start_absolute(self):
            del self._m_frame_work_area_start_absolute
        @property
        def frame_work_area_start_relative(self):
            """Work area start relative to composition start (frames)."""
            if hasattr(self, '_m_frame_work_area_start_relative'):
                return self._m_frame_work_area_start_relative

            self._m_frame_work_area_start_relative = self.frame_work_area_start_absolute - self.display_start_frame
            return getattr(self, '_m_frame_work_area_start_relative', None)

        def _invalidate_frame_work_area_start_relative(self):
            del self._m_frame_work_area_start_relative
        @property
        def pixel_aspect(self):
            if hasattr(self, '_m_pixel_aspect'):
                return self._m_pixel_aspect

            self._m_pixel_aspect = (self.pixel_ratio_dividend * 1.0) / self.pixel_ratio_divisor
            return getattr(self, '_m_pixel_aspect', None)

        def _invalidate_pixel_aspect(self):
            del self._m_pixel_aspect
        @property
        def time(self):
            if hasattr(self, '_m_time'):
                return self._m_time

            self._m_time = (self.time_dividend * 1.0) / self.time_divisor
            return getattr(self, '_m_time', None)

        def _invalidate_time(self):
            del self._m_time
        @property
        def time_scale(self):
            """Effective time scale combining integer and fractional parts.
            Used as divisor for keyframe time_raw to compute frame numbers.
            """
            if hasattr(self, '_m_time_scale'):
                return self._m_time_scale

            self._m_time_scale = self.time_scale_integer + (self.time_scale_fractional * 1.0) / 256
            return getattr(self, '_m_time_scale', None)

        def _invalidate_time_scale(self):
            del self._m_time_scale
        @property
        def work_area_duration(self):
            """Work area duration (seconds)."""
            if hasattr(self, '_m_work_area_duration'):
                return self._m_work_area_duration

            self._m_work_area_duration = self.work_area_end_absolute - self.work_area_start_absolute
            return getattr(self, '_m_work_area_duration', None)

        def _invalidate_work_area_duration(self):
            del self._m_work_area_duration
        @property
        def work_area_end_absolute(self):
            """Absolute work area end in composition time (seconds). Internal."""
            if hasattr(self, '_m_work_area_end_absolute'):
                return self._m_work_area_end_absolute

            self._m_work_area_end_absolute = (self.display_start_time + self.duration if self.work_area_end_dividend == 4294967295 else self.display_start_time + (self.work_area_end_dividend * 1.0) / self.work_area_end_divisor)
            return getattr(self, '_m_work_area_end_absolute', None)

        def _invalidate_work_area_end_absolute(self):
            del self._m_work_area_end_absolute
        @property
        def work_area_start_absolute(self):
            """Absolute work area start in composition time (seconds). Internal."""
            if hasattr(self, '_m_work_area_start_absolute'):
                return self._m_work_area_start_absolute

            self._m_work_area_start_absolute = self.display_start_time + (self.work_area_start_dividend * 1.0) / self.work_area_start_divisor
            return getattr(self, '_m_work_area_start_absolute', None)

        def _invalidate_work_area_start_absolute(self):
            del self._m_work_area_start_absolute
        @property
        def work_area_start_relative(self):
            """Work area start relative to composition start (seconds)."""
            if hasattr(self, '_m_work_area_start_relative'):
                return self._m_work_area_start_relative

            self._m_work_area_start_relative = self.work_area_start_absolute - self.display_start_time
            return getattr(self, '_m_work_area_start_relative', None)

        def _invalidate_work_area_start_relative(self):
            del self._m_work_area_start_relative

    class Chunk(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Chunk, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.chunk_type = (self._io.read_bytes(4)).decode(u"ASCII")
            self.len_body = self._io.read_u4be()
            _on = (u"" if  ((self.chunk_type == u"opti") and (self.len_body == 0))  else self.chunk_type)
            if _on == u"CCId":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CLId":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CTyp":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CapL":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CcCt":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CprC":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"CsCt":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"EfDC":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.EfdcBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"LIST":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.ListBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"NmHd":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.NmhdBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"RCom":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Chunks(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"RIFX":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.ListBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Roou":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.RoouBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Ropt":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.RoptBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Rout":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.RoutBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Smax":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.F8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Smin":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.F8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"StVS":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.U4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"Utf8":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Utf8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"acer":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.AcerBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"adfr":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.AdfrBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"alas":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Utf8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"apid":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.ApidBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"cdat":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.CdatBody(self._parent._parent._parent.list_type == u"otst", _io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"cdrp":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.CdrpBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"cdta":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.CdtaBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"cmta":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Utf8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"dwga":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.DwgaBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"ewot":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.EwotBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fcid":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FcidBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fdta":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FdtaBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fiac":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FiacBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fiop":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FiopBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fips":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FipsBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fitt":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FittBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fivc":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FivcBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fivi":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FiviBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fnam":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Chunks(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"foac":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FoacBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fott":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FittBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fovi":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.FoviBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"fth5":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Fth5Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"head":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.HeadBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"idta":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.IdtaBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"ipws":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.IpwsBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"ldat":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.LdatBody(self._parent.chunks[0].body.item_type, self._parent.chunks[0].body.item_size, self._parent.chunks[0].body.count, _io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"ldta":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.LdtaBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"lhd3":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Lhd3Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"linl":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.LinlBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"lnrb":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.LnrbBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"lnrp":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.LnrpBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"mkif":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.MkifBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"nnhd":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.NnhdBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"opti":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.OptiBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"otda":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.CdatBody(False, _io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"otln":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.OtlnBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"pard":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.PardBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"parn":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.ParnBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"pdnm":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Chunks(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"pjef":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Utf8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"prgb":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.PrgbBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"prin":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.PrinBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"shph":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.ShphBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"sspc":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.SspcBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdb4":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Tdb4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdli":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.S4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdmn":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Utf8Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdpi":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.S4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdps":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.S4Body(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdsb":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.TdsbBody(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdsn":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.Chunks(_io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tduM":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.TdumBody(self._parent.chunks[2].body.color, self._parent.chunks[2].body.integer, _io__raw_body, self, self._root)
                self.body._read()
            elif _on == u"tdum":
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.TdumBody(self._parent.chunks[2].body.color, self._parent.chunks[2].body.integer, _io__raw_body, self, self._root)
                self.body._read()
            else:
                pass
                self._raw_body = self._io.read_bytes(self.len_body)
                _io__raw_body = KaitaiStream(BytesIO(self._raw_body))
                self.body = Aep.AsciiBody(_io__raw_body, self, self._root)
                self.body._read()
            if self.len_body % 2 != 0:
                pass
                self.pad_byte = self._io.read_bytes(1)

            self._dirty = False


        def _fetch_instances(self):
            pass
            _on = (u"" if  ((self.chunk_type == u"opti") and (self.len_body == 0))  else self.chunk_type)
            if _on == u"CCId":
                pass
                self.body._fetch_instances()
            elif _on == u"CLId":
                pass
                self.body._fetch_instances()
            elif _on == u"CTyp":
                pass
                self.body._fetch_instances()
            elif _on == u"CapL":
                pass
                self.body._fetch_instances()
            elif _on == u"CcCt":
                pass
                self.body._fetch_instances()
            elif _on == u"CprC":
                pass
                self.body._fetch_instances()
            elif _on == u"CsCt":
                pass
                self.body._fetch_instances()
            elif _on == u"EfDC":
                pass
                self.body._fetch_instances()
            elif _on == u"LIST":
                pass
                self.body._fetch_instances()
            elif _on == u"NmHd":
                pass
                self.body._fetch_instances()
            elif _on == u"RCom":
                pass
                self.body._fetch_instances()
            elif _on == u"RIFX":
                pass
                self.body._fetch_instances()
            elif _on == u"Roou":
                pass
                self.body._fetch_instances()
            elif _on == u"Ropt":
                pass
                self.body._fetch_instances()
            elif _on == u"Rout":
                pass
                self.body._fetch_instances()
            elif _on == u"Smax":
                pass
                self.body._fetch_instances()
            elif _on == u"Smin":
                pass
                self.body._fetch_instances()
            elif _on == u"StVS":
                pass
                self.body._fetch_instances()
            elif _on == u"Utf8":
                pass
                self.body._fetch_instances()
            elif _on == u"acer":
                pass
                self.body._fetch_instances()
            elif _on == u"adfr":
                pass
                self.body._fetch_instances()
            elif _on == u"alas":
                pass
                self.body._fetch_instances()
            elif _on == u"apid":
                pass
                self.body._fetch_instances()
            elif _on == u"cdat":
                pass
                self.body._fetch_instances()
            elif _on == u"cdrp":
                pass
                self.body._fetch_instances()
            elif _on == u"cdta":
                pass
                self.body._fetch_instances()
            elif _on == u"cmta":
                pass
                self.body._fetch_instances()
            elif _on == u"dwga":
                pass
                self.body._fetch_instances()
            elif _on == u"ewot":
                pass
                self.body._fetch_instances()
            elif _on == u"fcid":
                pass
                self.body._fetch_instances()
            elif _on == u"fdta":
                pass
                self.body._fetch_instances()
            elif _on == u"fiac":
                pass
                self.body._fetch_instances()
            elif _on == u"fiop":
                pass
                self.body._fetch_instances()
            elif _on == u"fips":
                pass
                self.body._fetch_instances()
            elif _on == u"fitt":
                pass
                self.body._fetch_instances()
            elif _on == u"fivc":
                pass
                self.body._fetch_instances()
            elif _on == u"fivi":
                pass
                self.body._fetch_instances()
            elif _on == u"fnam":
                pass
                self.body._fetch_instances()
            elif _on == u"foac":
                pass
                self.body._fetch_instances()
            elif _on == u"fott":
                pass
                self.body._fetch_instances()
            elif _on == u"fovi":
                pass
                self.body._fetch_instances()
            elif _on == u"fth5":
                pass
                self.body._fetch_instances()
            elif _on == u"head":
                pass
                self.body._fetch_instances()
            elif _on == u"idta":
                pass
                self.body._fetch_instances()
            elif _on == u"ipws":
                pass
                self.body._fetch_instances()
            elif _on == u"ldat":
                pass
                self.body._fetch_instances()
            elif _on == u"ldta":
                pass
                self.body._fetch_instances()
            elif _on == u"lhd3":
                pass
                self.body._fetch_instances()
            elif _on == u"linl":
                pass
                self.body._fetch_instances()
            elif _on == u"lnrb":
                pass
                self.body._fetch_instances()
            elif _on == u"lnrp":
                pass
                self.body._fetch_instances()
            elif _on == u"mkif":
                pass
                self.body._fetch_instances()
            elif _on == u"nnhd":
                pass
                self.body._fetch_instances()
            elif _on == u"opti":
                pass
                self.body._fetch_instances()
            elif _on == u"otda":
                pass
                self.body._fetch_instances()
            elif _on == u"otln":
                pass
                self.body._fetch_instances()
            elif _on == u"pard":
                pass
                self.body._fetch_instances()
            elif _on == u"parn":
                pass
                self.body._fetch_instances()
            elif _on == u"pdnm":
                pass
                self.body._fetch_instances()
            elif _on == u"pjef":
                pass
                self.body._fetch_instances()
            elif _on == u"prgb":
                pass
                self.body._fetch_instances()
            elif _on == u"prin":
                pass
                self.body._fetch_instances()
            elif _on == u"shph":
                pass
                self.body._fetch_instances()
            elif _on == u"sspc":
                pass
                self.body._fetch_instances()
            elif _on == u"tdb4":
                pass
                self.body._fetch_instances()
            elif _on == u"tdli":
                pass
                self.body._fetch_instances()
            elif _on == u"tdmn":
                pass
                self.body._fetch_instances()
            elif _on == u"tdpi":
                pass
                self.body._fetch_instances()
            elif _on == u"tdps":
                pass
                self.body._fetch_instances()
            elif _on == u"tdsb":
                pass
                self.body._fetch_instances()
            elif _on == u"tdsn":
                pass
                self.body._fetch_instances()
            elif _on == u"tduM":
                pass
                self.body._fetch_instances()
            elif _on == u"tdum":
                pass
                self.body._fetch_instances()
            else:
                pass
                self.body._fetch_instances()
            if self.len_body % 2 != 0:
                pass



        def _write__seq(self, io=None):
            super(Aep.Chunk, self)._write__seq(io)
            self._io.write_bytes((self.chunk_type).encode(u"ASCII"))
            self._io.write_u4be(self.len_body)
            _on = (u"" if  ((self.chunk_type == u"opti") and (self.len_body == 0))  else self.chunk_type)
            if _on == u"CCId":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CLId":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CTyp":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CapL":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CcCt":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CprC":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"CsCt":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"EfDC":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"LIST":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"NmHd":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"RCom":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"RIFX":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Roou":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Ropt":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Rout":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Smax":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Smin":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"StVS":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"Utf8":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"acer":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"adfr":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"alas":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"apid":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"cdat":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"cdrp":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"cdta":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"cmta":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"dwga":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"ewot":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fcid":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fdta":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fiac":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fiop":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fips":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fitt":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fivc":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fivi":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fnam":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"foac":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fott":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fovi":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"fth5":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"head":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"idta":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"ipws":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"ldat":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"ldta":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"lhd3":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"linl":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"lnrb":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"lnrp":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"mkif":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"nnhd":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"opti":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"otda":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"otln":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"pard":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"parn":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"pdnm":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"pjef":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"prgb":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"prin":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"shph":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"sspc":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdb4":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdli":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdmn":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdpi":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdps":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdsb":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdsn":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tduM":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            elif _on == u"tdum":
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            else:
                pass
                _io__raw_body = KaitaiStream(BytesIO(bytearray(self.len_body)))
                self._io.add_child_stream(_io__raw_body)
                _pos2 = self._io.pos()
                self._io.seek(self._io.pos() + (self.len_body))
                def handler(parent, _io__raw_body=_io__raw_body):
                    self._raw_body = _io__raw_body.to_byte_array()
                    if len(self._raw_body) != self.len_body:
                        raise kaitaistruct.ConsistencyError(u"raw(body)", self.len_body, len(self._raw_body))
                    parent.write_bytes(self._raw_body)
                _io__raw_body.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                self.body._write__seq(_io__raw_body)
            if self.len_body % 2 != 0:
                pass
                self._io.write_bytes(self.pad_byte)



        def _check(self):
            if len((self.chunk_type).encode(u"ASCII")) != 4:
                raise kaitaistruct.ConsistencyError(u"chunk_type", 4, len((self.chunk_type).encode(u"ASCII")))
            _on = (u"" if  ((self.chunk_type == u"opti") and (self.len_body == 0))  else self.chunk_type)
            if _on == u"CCId":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CLId":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CTyp":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CapL":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CcCt":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CprC":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"CsCt":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"EfDC":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"LIST":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"NmHd":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"RCom":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"RIFX":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Roou":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Ropt":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Rout":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Smax":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Smin":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"StVS":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"Utf8":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"acer":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"adfr":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"alas":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"apid":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"cdat":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
                if self.body.is_le != (self._parent._parent._parent.list_type == u"otst"):
                    raise kaitaistruct.ConsistencyError(u"body", self._parent._parent._parent.list_type == u"otst", self.body.is_le)
            elif _on == u"cdrp":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"cdta":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"cmta":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"dwga":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"ewot":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fcid":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fdta":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fiac":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fiop":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fips":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fitt":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fivc":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fivi":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fnam":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"foac":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fott":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fovi":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"fth5":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"head":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"idta":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"ipws":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"ldat":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
                if self.body.item_type != self._parent.chunks[0].body.item_type:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[0].body.item_type, self.body.item_type)
                if self.body.item_size != self._parent.chunks[0].body.item_size:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[0].body.item_size, self.body.item_size)
                if self.body.count != self._parent.chunks[0].body.count:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[0].body.count, self.body.count)
            elif _on == u"ldta":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"lhd3":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"linl":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"lnrb":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"lnrp":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"mkif":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"nnhd":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"opti":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"otda":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
                if self.body.is_le != False:
                    raise kaitaistruct.ConsistencyError(u"body", False, self.body.is_le)
            elif _on == u"otln":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"pard":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"parn":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"pdnm":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"pjef":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"prgb":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"prin":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"shph":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"sspc":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdb4":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdli":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdmn":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdpi":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdps":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdsb":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tdsn":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"tduM":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
                if self.body.is_color != self._parent.chunks[2].body.color:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[2].body.color, self.body.is_color)
                if self.body.is_integer != self._parent.chunks[2].body.integer:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[2].body.integer, self.body.is_integer)
            elif _on == u"tdum":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
                if self.body.is_color != self._parent.chunks[2].body.color:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[2].body.color, self.body.is_color)
                if self.body.is_integer != self._parent.chunks[2].body.integer:
                    raise kaitaistruct.ConsistencyError(u"body", self._parent.chunks[2].body.integer, self.body.is_integer)
            else:
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            if self.len_body % 2 != 0:
                pass
                if len(self.pad_byte) != 1:
                    raise kaitaistruct.ConsistencyError(u"pad_byte", 1, len(self.pad_byte))

            self._dirty = False


    class Chunks(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Chunks, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.chunks = []
            i = 0
            while not self._io.is_eof():
                _t_chunks = Aep.Chunk(self._io, self, self._root)
                try:
                    _t_chunks._read()
                finally:
                    self.chunks.append(_t_chunks)
                i += 1

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.chunks)):
                pass
                self.chunks[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.Chunks, self)._write__seq(io)
            for i in range(len(self.chunks)):
                pass
                if self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"chunks", 0, self._io.size() - self._io.pos())
                self.chunks[i]._write__seq(self._io)

            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"chunks", 0, self._io.size() - self._io.pos())


        def _check(self):
            for i in range(len(self.chunks)):
                pass
                if self.chunks[i]._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"chunks", self._root, self.chunks[i]._root)
                if self.chunks[i]._parent != self:
                    raise kaitaistruct.ConsistencyError(u"chunks", self, self.chunks[i]._parent)

            self._dirty = False


    class CineonRoptData(ReadWriteKaitaiStruct):
        """Cineon/DPX format-specific render options (44 bytes after format code).
        These correspond to the Cineon Settings dialog in After Effects.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.CineonRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(6)
            self._unnamed1 = self._io.read_bytes(4)
            self.ten_bit_black_point = self._io.read_u2be()
            self.ten_bit_white_point = self._io.read_u2be()
            self.converted_black_point = self._io.read_f8be()
            self.converted_white_point = self._io.read_f8be()
            self.current_gamma = self._io.read_f8be()
            self.highlight_expansion = self._io.read_u2be()
            self.logarithmic_conversion = self._io.read_u1()
            self.file_format = self._io.read_u1()
            self.bit_depth = self._io.read_u1()
            self._unnamed11 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.CineonRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bytes(self._unnamed1)
            self._io.write_u2be(self.ten_bit_black_point)
            self._io.write_u2be(self.ten_bit_white_point)
            self._io.write_f8be(self.converted_black_point)
            self._io.write_f8be(self.converted_white_point)
            self._io.write_f8be(self.current_gamma)
            self._io.write_u2be(self.highlight_expansion)
            self._io.write_u1(self.logarithmic_conversion)
            self._io.write_u1(self.file_format)
            self._io.write_u1(self.bit_depth)
            self._io.write_bytes(self._unnamed11)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 6, len(self._unnamed0))
            if len(self._unnamed1) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 4, len(self._unnamed1))
            self._dirty = False


    class DwgaBody(ReadWriteKaitaiStruct):
        """Working gamma setting. Indicates the gamma value used for color management.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.DwgaBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.working_gamma_selector = self._io.read_u1()
            self._unnamed1 = self._io.read_bytes(3)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.DwgaBody, self)._write__seq(io)
            self._io.write_u1(self.working_gamma_selector)
            self._io.write_bytes(self._unnamed1)


        def _check(self):
            if len(self._unnamed1) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 3, len(self._unnamed1))
            self._dirty = False

        @property
        def working_gamma(self):
            """Working gamma value (2.2 or 2.4)."""
            if hasattr(self, '_m_working_gamma'):
                return self._m_working_gamma

            self._m_working_gamma = (2.4 if self.working_gamma_selector != 0 else 2.2)
            return getattr(self, '_m_working_gamma', None)

        def _invalidate_working_gamma(self):
            del self._m_working_gamma

    class EfdcBody(ReadWriteKaitaiStruct):
        """Effect definition count. The first byte contains the number of
        LIST EfDf definitions inside LIST EfdG.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.EfdcBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.count = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.EfdcBody, self)._write__seq(io)
            self._io.write_u1(self.count)


        def _check(self):
            self._dirty = False


    class EwotBody(ReadWriteKaitaiStruct):
        """Effect workspace outline entries inside LIST Ewst.
        Each entry is 4 bytes. The first byte contains flags:
          - bit 7 (0x80): child property of an effect (not an effect group)
          - bit 6 (0x40): selected
        Entries without bit 7 are effect-group-level nodes.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.EwotBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.num_entries = self._io.read_u4be()
            self.entries = []
            for i in range(self.num_entries):
                _t_entries = Aep.EwotEntry(self._io, self, self._root)
                try:
                    _t_entries._read()
                finally:
                    self.entries.append(_t_entries)

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.entries)):
                pass
                self.entries[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.EwotBody, self)._write__seq(io)
            self._io.write_u4be(self.num_entries)
            for i in range(len(self.entries)):
                pass
                self.entries[i]._write__seq(self._io)



        def _check(self):
            if len(self.entries) != self.num_entries:
                raise kaitaistruct.ConsistencyError(u"entries", self.num_entries, len(self.entries))
            for i in range(len(self.entries)):
                pass
                if self.entries[i]._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"entries", self._root, self.entries[i]._root)
                if self.entries[i]._parent != self:
                    raise kaitaistruct.ConsistencyError(u"entries", self, self.entries[i]._parent)

            self._dirty = False


    class EwotEntry(ReadWriteKaitaiStruct):
        """Single effect workspace outline entry."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.EwotEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.is_child_property = self._io.read_bits_int_be(1) != 0
            self.selected = self._io.read_bits_int_be(1) != 0
            self.reserved_flags = self._io.read_bits_int_be(6)
            self.data = self._io.read_bytes(3)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.EwotEntry, self)._write__seq(io)
            self._io.write_bits_int_be(1, int(self.is_child_property))
            self._io.write_bits_int_be(1, int(self.selected))
            self._io.write_bits_int_be(6, self.reserved_flags)
            self._io.write_bytes(self.data)


        def _check(self):
            if len(self.data) != 3:
                raise kaitaistruct.ConsistencyError(u"data", 3, len(self.data))
            self._dirty = False


    class F8Body(ReadWriteKaitaiStruct):
        """Single 64-bit floating-point value."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.F8Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.value = self._io.read_f8be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.F8Body, self)._write__seq(io)
            self._io.write_f8be(self.value)


        def _check(self):
            self._dirty = False


    class FcidBody(ReadWriteKaitaiStruct):
        """Active composition item ID. Stores the item ID of the currently
        active (most recently focused) composition in the project.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FcidBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.active_item_id = self._io.read_u4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FcidBody, self)._write__seq(io)
            self._io.write_u4be(self.active_item_id)


        def _check(self):
            self._dirty = False


    class FdtaBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FdtaBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(1)
            self._unnamed1 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FdtaBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bytes(self._unnamed1)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 1, len(self._unnamed0))
            self._dirty = False


    class FeatherPoint(ReadWriteKaitaiStruct):
        """A single variable-width mask feather point (32 bytes).
        The feather type (inner/outer) is derived from the sign of the radius:
        negative radius = inner feather (type 1), positive = outer (type 0).
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FeatherPoint, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.seg_loc = self._io.read_u4le()
            self.interp_raw = self._io.read_u4le()
            self.rel_seg_loc = self._io.read_f8be()
            self.radius = self._io.read_f8be()
            self.corner_angle = self._io.read_f4be()
            self.tension = self._io.read_f4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FeatherPoint, self)._write__seq(io)
            self._io.write_u4le(self.seg_loc)
            self._io.write_u4le(self.interp_raw)
            self._io.write_f8be(self.rel_seg_loc)
            self._io.write_f8be(self.radius)
            self._io.write_f4be(self.corner_angle)
            self._io.write_f4be(self.tension)


        def _check(self):
            self._dirty = False


    class FiacBody(ReadWriteKaitaiStruct):
        """Viewer inner tab active flag. Not a focus indicator - does not
        change when clicking different panels.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FiacBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.active = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FiacBody, self)._write__seq(io)
            self._io.write_u1(self.active)


        def _check(self):
            self._dirty = False


    class FiopBody(ReadWriteKaitaiStruct):
        """Viewer panel open flag. When 1, the panel is open and visible.
        Blocks without fitt are ghost/closed entries.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FiopBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.open = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FiopBody, self)._write__seq(io)
            self._io.write_u1(self.open)


        def _check(self):
            self._dirty = False


    class FipsBody(ReadWriteKaitaiStruct):
        """Folder item panel settings. Stores viewer panel state including
        Draft 3D mode, view options (channels, exposure, zoom, etc.), and
        toggle flags (guides, rulers, grid, etc.). There are typically 4
        fips chunks per viewer group, one for each AE composition viewer
        panel. Total size is 96 bytes.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FipsBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(7)
            self.channels = self._io.read_u1()
            self._unnamed2 = self._io.read_bytes(3)
            self._unnamed3 = self._io.read_bits_int_be(6)
            self.proportional_grid = self._io.read_bits_int_be(1) != 0
            self.title_action_safe = self._io.read_bits_int_be(1) != 0
            self._unnamed6 = self._io.read_bits_int_be(5)
            self.draft3d = self._io.read_bits_int_be(1) != 0
            self._unnamed8 = self._io.read_bits_int_be(2)
            self._unnamed9 = self._io.read_bits_int_be(3)
            self.fast_preview_draft = self._io.read_bits_int_be(1) != 0
            self._unnamed11 = self._io.read_bits_int_be(1) != 0
            self.fast_preview_fast_draft = self._io.read_bits_int_be(1) != 0
            self._unnamed13 = self._io.read_bits_int_be(1) != 0
            self.fast_preview_adaptive = self._io.read_bits_int_be(1) != 0
            self.region_of_interest = self._io.read_bits_int_be(1) != 0
            self.rulers = self._io.read_bits_int_be(1) != 0
            self._unnamed17 = self._io.read_bits_int_be(1) != 0
            self.fast_preview_wireframe = self._io.read_bits_int_be(1) != 0
            self._unnamed19 = self._io.read_bits_int_be(4)
            self.checkerboards = self._io.read_bits_int_be(1) != 0
            self._unnamed21 = self._io.read_bits_int_be(2)
            self.mask_and_shape_path = self._io.read_bits_int_be(1) != 0
            self._unnamed23 = self._io.read_bits_int_be(4)
            self._unnamed24 = self._io.read_bytes(7)
            self._unnamed25 = self._io.read_bits_int_be(4)
            self.grid = self._io.read_bits_int_be(1) != 0
            self.guides_snap = self._io.read_bits_int_be(1) != 0
            self.guides_locked = self._io.read_bits_int_be(1) != 0
            self.guides_visibility = self._io.read_bits_int_be(1) != 0
            self._unnamed30 = self._io.read_bytes(16)
            self.roi_top = self._io.read_u2be()
            self.roi_left = self._io.read_u2be()
            self.roi_bottom = self._io.read_u2be()
            self.roi_right = self._io.read_u2be()
            self._unnamed35 = self._io.read_bytes(21)
            self.zoom_type = self._io.read_u1()
            self._unnamed37 = self._io.read_bytes(2)
            self.zoom = self._io.read_f8be()
            self.exposure = self._io.read_f4be()
            self._unnamed40 = self._io.read_bytes(1)
            self._unnamed41 = self._io.read_bits_int_be(7)
            self.use_display_color_management = self._io.read_bits_int_be(1) != 0
            self._unnamed43 = self._io.read_bits_int_be(7)
            self.auto_resolution = self._io.read_bits_int_be(1) != 0
            self._unnamed45 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FipsBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u1(self.channels)
            self._io.write_bytes(self._unnamed2)
            self._io.write_bits_int_be(6, self._unnamed3)
            self._io.write_bits_int_be(1, int(self.proportional_grid))
            self._io.write_bits_int_be(1, int(self.title_action_safe))
            self._io.write_bits_int_be(5, self._unnamed6)
            self._io.write_bits_int_be(1, int(self.draft3d))
            self._io.write_bits_int_be(2, self._unnamed8)
            self._io.write_bits_int_be(3, self._unnamed9)
            self._io.write_bits_int_be(1, int(self.fast_preview_draft))
            self._io.write_bits_int_be(1, int(self._unnamed11))
            self._io.write_bits_int_be(1, int(self.fast_preview_fast_draft))
            self._io.write_bits_int_be(1, int(self._unnamed13))
            self._io.write_bits_int_be(1, int(self.fast_preview_adaptive))
            self._io.write_bits_int_be(1, int(self.region_of_interest))
            self._io.write_bits_int_be(1, int(self.rulers))
            self._io.write_bits_int_be(1, int(self._unnamed17))
            self._io.write_bits_int_be(1, int(self.fast_preview_wireframe))
            self._io.write_bits_int_be(4, self._unnamed19)
            self._io.write_bits_int_be(1, int(self.checkerboards))
            self._io.write_bits_int_be(2, self._unnamed21)
            self._io.write_bits_int_be(1, int(self.mask_and_shape_path))
            self._io.write_bits_int_be(4, self._unnamed23)
            self._io.write_bytes(self._unnamed24)
            self._io.write_bits_int_be(4, self._unnamed25)
            self._io.write_bits_int_be(1, int(self.grid))
            self._io.write_bits_int_be(1, int(self.guides_snap))
            self._io.write_bits_int_be(1, int(self.guides_locked))
            self._io.write_bits_int_be(1, int(self.guides_visibility))
            self._io.write_bytes(self._unnamed30)
            self._io.write_u2be(self.roi_top)
            self._io.write_u2be(self.roi_left)
            self._io.write_u2be(self.roi_bottom)
            self._io.write_u2be(self.roi_right)
            self._io.write_bytes(self._unnamed35)
            self._io.write_u1(self.zoom_type)
            self._io.write_bytes(self._unnamed37)
            self._io.write_f8be(self.zoom)
            self._io.write_f4be(self.exposure)
            self._io.write_bytes(self._unnamed40)
            self._io.write_bits_int_be(7, self._unnamed41)
            self._io.write_bits_int_be(1, int(self.use_display_color_management))
            self._io.write_bits_int_be(7, self._unnamed43)
            self._io.write_bits_int_be(1, int(self.auto_resolution))
            self._io.write_bytes(self._unnamed45)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed45", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 7, len(self._unnamed0))
            if len(self._unnamed2) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 3, len(self._unnamed2))
            if len(self._unnamed24) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed24", 7, len(self._unnamed24))
            if len(self._unnamed30) != 16:
                raise kaitaistruct.ConsistencyError(u"_unnamed30", 16, len(self._unnamed30))
            if len(self._unnamed35) != 21:
                raise kaitaistruct.ConsistencyError(u"_unnamed35", 21, len(self._unnamed35))
            if len(self._unnamed37) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed37", 2, len(self._unnamed37))
            if len(self._unnamed40) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed40", 1, len(self._unnamed40))
            self._dirty = False

        @property
        def fast_preview_type(self):
            """Computed fast preview type from individual binary flags.
            0=off, 1=adaptive_resolution, 2=draft, 3=fast_draft, 4=wireframe.
            """
            if hasattr(self, '_m_fast_preview_type'):
                return self._m_fast_preview_type

            self._m_fast_preview_type = KaitaiStream.resolve_enum(Aep.FastPreviewType, (4 if self.fast_preview_wireframe else (3 if self.fast_preview_fast_draft else (2 if self.fast_preview_draft else (1 if self.fast_preview_adaptive else 0)))))
            return getattr(self, '_m_fast_preview_type', None)

        def _invalidate_fast_preview_type(self):
            del self._m_fast_preview_type

    class FittBody(ReadWriteKaitaiStruct):
        """Viewer inner tab type label. An ASCII string identifying the
        viewer type (e.g. "AE Composition", "AE Layer", "AE Footage").
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FittBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.label = (self._io.read_bytes_full()).decode(u"ASCII")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FittBody, self)._write__seq(io)
            self._io.write_bytes((self.label).encode(u"ASCII"))
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"label", 0, self._io.size() - self._io.pos())


        def _check(self):
            self._dirty = False


    class FivcBody(ReadWriteKaitaiStruct):
        """Locked view count. Counts views created via "View > Split with
        New Locked View" (1=single, 2=split). Does NOT count 3D
        viewports - the 3D viewport layout is stored inside fips.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FivcBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.view_count = self._io.read_u2be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FivcBody, self)._write__seq(io)
            self._io.write_u2be(self.view_count)


        def _check(self):
            self._dirty = False


    class FiviBody(ReadWriteKaitaiStruct):
        """Per-view sequential identity. One fivi chunk per locked view
        (as counted by fivc). Not an active view indicator.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FiviBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.identity = self._io.read_u4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FiviBody, self)._write__seq(io)
            self._io.write_u4be(self.identity)


        def _check(self):
            self._dirty = False


    class FoacBody(ReadWriteKaitaiStruct):
        """Viewer outer tab active flag. Not a focus indicator - does not
        change when clicking different panels.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FoacBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.active = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FoacBody, self)._write__seq(io)
            self._io.write_u1(self.active)


        def _check(self):
            self._dirty = False


    class FoviBody(ReadWriteKaitaiStruct):
        """Viewer item index. A zero-based positional index into the LIST:Item
        children at the same folder level, mapping this viewer to its
        associated composition or footage item.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.FoviBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.item_index = self._io.read_u4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.FoviBody, self)._write__seq(io)
            self._io.write_u4be(self.item_index)


        def _check(self):
            self._dirty = False


    class Fth5Body(ReadWriteKaitaiStruct):
        """Variable-width mask feather points.  Each feather point is 32 bytes.
        Feather points can be placed anywhere along a closed mask path to vary
        the feather radius at different positions.  The number of points is
        determined by the chunk size divided by 32.
        
        Integer fields use little-endian byte order despite the big-endian
        RIFX container (similar to OTST cdat).  Float fields remain big-endian.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Fth5Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.points = []
            i = 0
            while not self._io.is_eof():
                _t_points = Aep.FeatherPoint(self._io, self, self._root)
                try:
                    _t_points._read()
                finally:
                    self.points.append(_t_points)
                i += 1

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.points)):
                pass
                self.points[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.Fth5Body, self)._write__seq(io)
            for i in range(len(self.points)):
                pass
                if self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"points", 0, self._io.size() - self._io.pos())
                self.points[i]._write__seq(self._io)

            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"points", 0, self._io.size() - self._io.pos())


        def _check(self):
            for i in range(len(self.points)):
                pass
                if self.points[i]._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"points", self._root, self.points[i]._root)
                if self.points[i]._parent != self:
                    raise kaitaistruct.ConsistencyError(u"points", self, self.points[i]._parent)

            self._dirty = False


    class GuideItem(ReadWriteKaitaiStruct):
        """A single guide item (16 bytes) inside LIST:Gide/LIST:list/ldat.
        Guides are ruler lines used for alignment in compositions.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.GuideItem, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.orientation_type = self._io.read_u4be()
            self.position_type = self._io.read_u4be()
            self.position = self._io.read_f8be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.GuideItem, self)._write__seq(io)
            self._io.write_u4be(self.orientation_type)
            self._io.write_u4be(self.position_type)
            self._io.write_f8be(self.position)


        def _check(self):
            self._dirty = False


    class HeadBody(ReadWriteKaitaiStruct):
        """After Effects file header. Contains version info encoded as a 32-bit value.
        Major version = MAJOR-A * 8 + MAJOR-B
        See: https://github.com/tinogithub/aftereffects-version-check
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.HeadBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(4)
            self._unnamed1 = self._io.read_bits_int_be(1) != 0
            self.ae_version_major_a = self._io.read_bits_int_be(5)
            self.ae_version_os = self._io.read_bits_int_be(4)
            self.ae_version_major_b = self._io.read_bits_int_be(3)
            self.ae_version_minor = self._io.read_bits_int_be(4)
            self.ae_version_patch = self._io.read_bits_int_be(4)
            self._unnamed7 = self._io.read_bits_int_be(1) != 0
            self.ae_version_beta_flag = self._io.read_bits_int_be(1) != 0
            self._unnamed9 = self._io.read_bits_int_be(1) != 0
            self.ae_build_number = self._io.read_bits_int_be(8)
            self._unnamed11 = self._io.read_bytes(10)
            self.file_revision = self._io.read_u2be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.HeadBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(1, int(self._unnamed1))
            self._io.write_bits_int_be(5, self.ae_version_major_a)
            self._io.write_bits_int_be(4, self.ae_version_os)
            self._io.write_bits_int_be(3, self.ae_version_major_b)
            self._io.write_bits_int_be(4, self.ae_version_minor)
            self._io.write_bits_int_be(4, self.ae_version_patch)
            self._io.write_bits_int_be(1, int(self._unnamed7))
            self._io.write_bits_int_be(1, int(self.ae_version_beta_flag))
            self._io.write_bits_int_be(1, int(self._unnamed9))
            self._io.write_bits_int_be(8, self.ae_build_number)
            self._io.write_bytes(self._unnamed11)
            self._io.write_u2be(self.file_revision)


        def _check(self):
            if len(self._unnamed0) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 4, len(self._unnamed0))
            if len(self._unnamed11) != 10:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 10, len(self._unnamed11))
            self._dirty = False

        @property
        def ae_version_beta(self):
            """True if beta version."""
            if hasattr(self, '_m_ae_version_beta'):
                return self._m_ae_version_beta

            self._m_ae_version_beta = (not (self.ae_version_beta_flag))
            return getattr(self, '_m_ae_version_beta', None)

        def _invalidate_ae_version_beta(self):
            del self._m_ae_version_beta
        @property
        def ae_version_major(self):
            """Full major version number (e.g., 25)."""
            if hasattr(self, '_m_ae_version_major'):
                return self._m_ae_version_major

            self._m_ae_version_major = self.ae_version_major_a * 8 + self.ae_version_major_b
            return getattr(self, '_m_ae_version_major', None)

        def _invalidate_ae_version_major(self):
            del self._m_ae_version_major
        @property
        def version(self):
            if hasattr(self, '_m_version'):
                return self._m_version

            self._m_version = str(self.ae_version_major) + u"." + str(self.ae_version_minor) + u"x" + str(self.ae_build_number)
            return getattr(self, '_m_version', None)

        def _invalidate_version(self):
            del self._m_version

    class IdtaBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.IdtaBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.item_type = KaitaiStream.resolve_enum(Aep.ItemType, self._io.read_u2be())
            self._unnamed1 = self._io.read_bytes(14)
            self.item_id = self._io.read_u4be()
            self._unnamed3 = self._io.read_bytes(4)
            self._unnamed4 = self._io.read_bytes(34)
            self.label = KaitaiStream.resolve_enum(Aep.Label, self._io.read_u1())
            self._unnamed6 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.IdtaBody, self)._write__seq(io)
            self._io.write_u2be(int(self.item_type))
            self._io.write_bytes(self._unnamed1)
            self._io.write_u4be(self.item_id)
            self._io.write_bytes(self._unnamed3)
            self._io.write_bytes(self._unnamed4)
            self._io.write_u1(int(self.label))
            self._io.write_bytes(self._unnamed6)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed1) != 14:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 14, len(self._unnamed1))
            if len(self._unnamed3) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed3", 4, len(self._unnamed3))
            if len(self._unnamed4) != 34:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 34, len(self._unnamed4))
            self._dirty = False


    class IpwsBody(ReadWriteKaitaiStruct):
        """Interpret footage as project working space flag.
        Inside LIST:CLRS in a footage item's LIST:Pin.
        When enabled (1), the footage media color space is overridden
        to use the project's working color space.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.IpwsBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.enabled = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.IpwsBody, self)._write__seq(io)
            self._io.write_u1(self.enabled)


        def _check(self):
            self._dirty = False


    class JpegRoptData(ReadWriteKaitaiStruct):
        """JPEG format-specific render options (54 bytes after format code).
        The first 48 bytes are a static header/magic block. The last 6 bytes
        hold quality, format type, and scans as u16 values.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.JpegRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(48)
            self.quality = self._io.read_u2be()
            self.format_type = self._io.read_u2be()
            self.scans = self._io.read_u2be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.JpegRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u2be(self.quality)
            self._io.write_u2be(self.format_type)
            self._io.write_u2be(self.scans)


        def _check(self):
            if len(self._unnamed0) != 48:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 48, len(self._unnamed0))
            self._dirty = False


    class KfColor(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.KfColor, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_u8be()
            self._unnamed1 = self._io.read_f8be()
            self.in_speed = self._io.read_f8be()
            self.in_influence = self._io.read_f8be()
            self.out_speed = self._io.read_f8be()
            self.out_influence = self._io.read_f8be()
            self.value = []
            for i in range(4):
                self.value.append(self._io.read_f8be())

            self._unnamed7 = []
            for i in range(8):
                self._unnamed7.append(self._io.read_f8be())

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.value)):
                pass

            for i in range(len(self._unnamed7)):
                pass



        def _write__seq(self, io=None):
            super(Aep.KfColor, self)._write__seq(io)
            self._io.write_u8be(self._unnamed0)
            self._io.write_f8be(self._unnamed1)
            self._io.write_f8be(self.in_speed)
            self._io.write_f8be(self.in_influence)
            self._io.write_f8be(self.out_speed)
            self._io.write_f8be(self.out_influence)
            for i in range(len(self.value)):
                pass
                self._io.write_f8be(self.value[i])

            for i in range(len(self._unnamed7)):
                pass
                self._io.write_f8be(self._unnamed7[i])



        def _check(self):
            if len(self.value) != 4:
                raise kaitaistruct.ConsistencyError(u"value", 4, len(self.value))
            for i in range(len(self.value)):
                pass

            if len(self._unnamed7) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 8, len(self._unnamed7))
            for i in range(len(self._unnamed7)):
                pass

            self._dirty = False


    class KfMultiDimensional(ReadWriteKaitaiStruct):
        def __init__(self, num_value, _io=None, _parent=None, _root=None):
            super(Aep.KfMultiDimensional, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.num_value = num_value

        def _read(self):
            self.value = []
            for i in range(self.num_value):
                self.value.append(self._io.read_f8be())

            self.in_speed = []
            for i in range(self.num_value):
                self.in_speed.append(self._io.read_f8be())

            self.in_influence = []
            for i in range(self.num_value):
                self.in_influence.append(self._io.read_f8be())

            self.out_speed = []
            for i in range(self.num_value):
                self.out_speed.append(self._io.read_f8be())

            self.out_influence = []
            for i in range(self.num_value):
                self.out_influence.append(self._io.read_f8be())

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.value)):
                pass

            for i in range(len(self.in_speed)):
                pass

            for i in range(len(self.in_influence)):
                pass

            for i in range(len(self.out_speed)):
                pass

            for i in range(len(self.out_influence)):
                pass



        def _write__seq(self, io=None):
            super(Aep.KfMultiDimensional, self)._write__seq(io)
            for i in range(len(self.value)):
                pass
                self._io.write_f8be(self.value[i])

            for i in range(len(self.in_speed)):
                pass
                self._io.write_f8be(self.in_speed[i])

            for i in range(len(self.in_influence)):
                pass
                self._io.write_f8be(self.in_influence[i])

            for i in range(len(self.out_speed)):
                pass
                self._io.write_f8be(self.out_speed[i])

            for i in range(len(self.out_influence)):
                pass
                self._io.write_f8be(self.out_influence[i])



        def _check(self):
            if len(self.value) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"value", self.num_value, len(self.value))
            for i in range(len(self.value)):
                pass

            if len(self.in_speed) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"in_speed", self.num_value, len(self.in_speed))
            for i in range(len(self.in_speed)):
                pass

            if len(self.in_influence) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"in_influence", self.num_value, len(self.in_influence))
            for i in range(len(self.in_influence)):
                pass

            if len(self.out_speed) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"out_speed", self.num_value, len(self.out_speed))
            for i in range(len(self.out_speed)):
                pass

            if len(self.out_influence) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"out_influence", self.num_value, len(self.out_influence))
            for i in range(len(self.out_influence)):
                pass

            self._dirty = False


    class KfNoValue(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.KfNoValue, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_u8be()
            self._unnamed1 = self._io.read_f8be()
            self.in_speed = self._io.read_f8be()
            self.in_influence = self._io.read_f8be()
            self.out_speed = self._io.read_f8be()
            self.out_influence = self._io.read_f8be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.KfNoValue, self)._write__seq(io)
            self._io.write_u8be(self._unnamed0)
            self._io.write_f8be(self._unnamed1)
            self._io.write_f8be(self.in_speed)
            self._io.write_f8be(self.in_influence)
            self._io.write_f8be(self.out_speed)
            self._io.write_f8be(self.out_influence)


        def _check(self):
            self._dirty = False


    class KfPosition(ReadWriteKaitaiStruct):
        def __init__(self, num_value, _io=None, _parent=None, _root=None):
            super(Aep.KfPosition, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.num_value = num_value

        def _read(self):
            self._unnamed0 = self._io.read_bytes(3)
            self._unnamed1 = self._io.read_bits_int_be(6)
            self.spatial_auto_bezier = self._io.read_bits_int_be(1) != 0
            self.spatial_continuous = self._io.read_bits_int_be(1) != 0
            self._unnamed4 = self._io.read_bytes(4)
            self._unnamed5 = self._io.read_f8be()
            self.in_speed = self._io.read_f8be()
            self.in_influence = self._io.read_f8be()
            self.out_speed = self._io.read_f8be()
            self.out_influence = self._io.read_f8be()
            self.value = []
            for i in range(self.num_value):
                self.value.append(self._io.read_f8be())

            self.in_spatial_tangents = []
            for i in range(self.num_value):
                self.in_spatial_tangents.append(self._io.read_f8be())

            self.out_spatial_tangents = []
            for i in range(self.num_value):
                self.out_spatial_tangents.append(self._io.read_f8be())

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.value)):
                pass

            for i in range(len(self.in_spatial_tangents)):
                pass

            for i in range(len(self.out_spatial_tangents)):
                pass



        def _write__seq(self, io=None):
            super(Aep.KfPosition, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(6, self._unnamed1)
            self._io.write_bits_int_be(1, int(self.spatial_auto_bezier))
            self._io.write_bits_int_be(1, int(self.spatial_continuous))
            self._io.write_bytes(self._unnamed4)
            self._io.write_f8be(self._unnamed5)
            self._io.write_f8be(self.in_speed)
            self._io.write_f8be(self.in_influence)
            self._io.write_f8be(self.out_speed)
            self._io.write_f8be(self.out_influence)
            for i in range(len(self.value)):
                pass
                self._io.write_f8be(self.value[i])

            for i in range(len(self.in_spatial_tangents)):
                pass
                self._io.write_f8be(self.in_spatial_tangents[i])

            for i in range(len(self.out_spatial_tangents)):
                pass
                self._io.write_f8be(self.out_spatial_tangents[i])



        def _check(self):
            if len(self._unnamed0) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 3, len(self._unnamed0))
            if len(self._unnamed4) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 4, len(self._unnamed4))
            if len(self.value) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"value", self.num_value, len(self.value))
            for i in range(len(self.value)):
                pass

            if len(self.in_spatial_tangents) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"in_spatial_tangents", self.num_value, len(self.in_spatial_tangents))
            for i in range(len(self.in_spatial_tangents)):
                pass

            if len(self.out_spatial_tangents) != self.num_value:
                raise kaitaistruct.ConsistencyError(u"out_spatial_tangents", self.num_value, len(self.out_spatial_tangents))
            for i in range(len(self.out_spatial_tangents)):
                pass

            self._dirty = False


    class KfUnknownData(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.KfUnknownData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.contents = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.KfUnknownData, self)._write__seq(io)
            self._io.write_bytes(self.contents)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"contents", 0, self._io.size() - self._io.pos())


        def _check(self):
            self._dirty = False


    class LdatBody(ReadWriteKaitaiStruct):
        """Keyframe / shape / settings data items. Typed via params from sibling lhd3.
        Automatically promotes three_d to three_d_spatial when the parent tdbs
        context indicates the property is spatial (tdb4.is_spatial).
        """
        def __init__(self, item_type, item_size, count, _io=None, _parent=None, _root=None):
            super(Aep.LdatBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.item_type = item_type
            self.item_size = item_size
            self.count = count

        def _read(self):
            self._raw_items = []
            self.items = []
            for i in range(self.count):
                _on = self.effective_item_type
                if _on == Aep.LdatItemType.gide:
                    pass
                    self._raw_items.append(self._io.read_bytes(self.item_size))
                    _io__raw_items = KaitaiStream(BytesIO(self._raw_items[i]))
                    _t_items = Aep.GuideItem(_io__raw_items, self, self._root)
                    try:
                        _t_items._read()
                    finally:
                        self.items.append(_t_items)
                elif _on == Aep.LdatItemType.litm:
                    pass
                    self._raw_items.append(self._io.read_bytes(self.item_size))
                    _io__raw_items = KaitaiStream(BytesIO(self._raw_items[i]))
                    _t_items = Aep.OutputModuleSettingsLdatBody(_io__raw_items, self, self._root)
                    try:
                        _t_items._read()
                    finally:
                        self.items.append(_t_items)
                elif _on == Aep.LdatItemType.lrdr:
                    pass
                    self._raw_items.append(self._io.read_bytes(self.item_size))
                    _io__raw_items = KaitaiStream(BytesIO(self._raw_items[i]))
                    _t_items = Aep.RenderSettingsLdatBody(_io__raw_items, self, self._root)
                    try:
                        _t_items._read()
                    finally:
                        self.items.append(_t_items)
                elif _on == Aep.LdatItemType.shape:
                    pass
                    self._raw_items.append(self._io.read_bytes(self.item_size))
                    _io__raw_items = KaitaiStream(BytesIO(self._raw_items[i]))
                    _t_items = Aep.ShapePoint(_io__raw_items, self, self._root)
                    try:
                        _t_items._read()
                    finally:
                        self.items.append(_t_items)
                else:
                    pass
                    self._raw_items.append(self._io.read_bytes(self.item_size))
                    _io__raw_items = KaitaiStream(BytesIO(self._raw_items[i]))
                    _t_items = Aep.LdatItem(self.effective_item_type, _io__raw_items, self, self._root)
                    try:
                        _t_items._read()
                    finally:
                        self.items.append(_t_items)

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.items)):
                pass
                _on = self.effective_item_type
                if _on == Aep.LdatItemType.gide:
                    pass
                    self.items[i]._fetch_instances()
                elif _on == Aep.LdatItemType.litm:
                    pass
                    self.items[i]._fetch_instances()
                elif _on == Aep.LdatItemType.lrdr:
                    pass
                    self.items[i]._fetch_instances()
                elif _on == Aep.LdatItemType.shape:
                    pass
                    self.items[i]._fetch_instances()
                else:
                    pass
                    self.items[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.LdatBody, self)._write__seq(io)
            self._raw_items = []
            for i in range(len(self.items)):
                pass
                _on = self.effective_item_type
                if _on == Aep.LdatItemType.gide:
                    pass
                    _io__raw_items = KaitaiStream(BytesIO(bytearray(self.item_size)))
                    self._io.add_child_stream(_io__raw_items)
                    _pos2 = self._io.pos()
                    self._io.seek(self._io.pos() + (self.item_size))
                    def handler(parent, _io__raw_items=_io__raw_items, i=i):
                        self._raw_items.append(_io__raw_items.to_byte_array())
                        if len(self._raw_items[i]) != self.item_size:
                            raise kaitaistruct.ConsistencyError(u"raw(items)", self.item_size, len(self._raw_items[i]))
                        parent.write_bytes(self._raw_items[i])
                    _io__raw_items.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                    self.items[i]._write__seq(_io__raw_items)
                elif _on == Aep.LdatItemType.litm:
                    pass
                    _io__raw_items = KaitaiStream(BytesIO(bytearray(self.item_size)))
                    self._io.add_child_stream(_io__raw_items)
                    _pos2 = self._io.pos()
                    self._io.seek(self._io.pos() + (self.item_size))
                    def handler(parent, _io__raw_items=_io__raw_items, i=i):
                        self._raw_items.append(_io__raw_items.to_byte_array())
                        if len(self._raw_items[i]) != self.item_size:
                            raise kaitaistruct.ConsistencyError(u"raw(items)", self.item_size, len(self._raw_items[i]))
                        parent.write_bytes(self._raw_items[i])
                    _io__raw_items.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                    self.items[i]._write__seq(_io__raw_items)
                elif _on == Aep.LdatItemType.lrdr:
                    pass
                    _io__raw_items = KaitaiStream(BytesIO(bytearray(self.item_size)))
                    self._io.add_child_stream(_io__raw_items)
                    _pos2 = self._io.pos()
                    self._io.seek(self._io.pos() + (self.item_size))
                    def handler(parent, _io__raw_items=_io__raw_items, i=i):
                        self._raw_items.append(_io__raw_items.to_byte_array())
                        if len(self._raw_items[i]) != self.item_size:
                            raise kaitaistruct.ConsistencyError(u"raw(items)", self.item_size, len(self._raw_items[i]))
                        parent.write_bytes(self._raw_items[i])
                    _io__raw_items.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                    self.items[i]._write__seq(_io__raw_items)
                elif _on == Aep.LdatItemType.shape:
                    pass
                    _io__raw_items = KaitaiStream(BytesIO(bytearray(self.item_size)))
                    self._io.add_child_stream(_io__raw_items)
                    _pos2 = self._io.pos()
                    self._io.seek(self._io.pos() + (self.item_size))
                    def handler(parent, _io__raw_items=_io__raw_items, i=i):
                        self._raw_items.append(_io__raw_items.to_byte_array())
                        if len(self._raw_items[i]) != self.item_size:
                            raise kaitaistruct.ConsistencyError(u"raw(items)", self.item_size, len(self._raw_items[i]))
                        parent.write_bytes(self._raw_items[i])
                    _io__raw_items.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                    self.items[i]._write__seq(_io__raw_items)
                else:
                    pass
                    _io__raw_items = KaitaiStream(BytesIO(bytearray(self.item_size)))
                    self._io.add_child_stream(_io__raw_items)
                    _pos2 = self._io.pos()
                    self._io.seek(self._io.pos() + (self.item_size))
                    def handler(parent, _io__raw_items=_io__raw_items, i=i):
                        self._raw_items.append(_io__raw_items.to_byte_array())
                        if len(self._raw_items[i]) != self.item_size:
                            raise kaitaistruct.ConsistencyError(u"raw(items)", self.item_size, len(self._raw_items[i]))
                        parent.write_bytes(self._raw_items[i])
                    _io__raw_items.write_back_handler = KaitaiStream.WriteBackHandler(_pos2, handler)
                    self.items[i]._write__seq(_io__raw_items)



        def _check(self):
            if len(self.items) != self.count:
                raise kaitaistruct.ConsistencyError(u"items", self.count, len(self.items))
            for i in range(len(self.items)):
                pass
                _on = self.effective_item_type
                if _on == Aep.LdatItemType.gide:
                    pass
                    if self.items[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                    if self.items[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)
                elif _on == Aep.LdatItemType.litm:
                    pass
                    if self.items[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                    if self.items[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)
                elif _on == Aep.LdatItemType.lrdr:
                    pass
                    if self.items[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                    if self.items[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)
                elif _on == Aep.LdatItemType.shape:
                    pass
                    if self.items[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                    if self.items[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)
                else:
                    pass
                    if self.items[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                    if self.items[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)
                    if self.items[i].item_type != self.effective_item_type:
                        raise kaitaistruct.ConsistencyError(u"items", self.effective_item_type, self.items[i].item_type)

            self._dirty = False

        @property
        def effective_item_type(self):
            """Promotes three_d to three_d_spatial for spatial properties.
            Both have item_size=128 but different binary layouts (kf_multi_dimensional vs kf_position).
            """
            if hasattr(self, '_m_effective_item_type'):
                return self._m_effective_item_type

            self._m_effective_item_type = (Aep.LdatItemType.three_d_spatial if  ((self.item_type == Aep.LdatItemType.three_d) and (self.is_spatial))  else self.item_type)
            return getattr(self, '_m_effective_item_type', None)

        def _invalidate_effective_item_type(self):
            del self._m_effective_item_type
        @property
        def is_spatial(self):
            """Whether the parent property is spatial (from tdb4 in the grandparent LIST:tdbs)."""
            if hasattr(self, '_m_is_spatial'):
                return self._m_is_spatial

            self._m_is_spatial =  ((self._parent._parent._parent._parent.list_type == u"tdbs") and (self._parent._parent._parent._parent.chunks[2].body.is_spatial)) 
            return getattr(self, '_m_is_spatial', None)

        def _invalidate_is_spatial(self):
            del self._m_is_spatial

    class LdatItem(ReadWriteKaitaiStruct):
        def __init__(self, item_type, _io=None, _parent=None, _root=None):
            super(Aep.LdatItem, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.item_type = item_type

        def _read(self):
            self._unnamed0 = self._io.read_bytes(1)
            self.time_raw = self._io.read_s2be()
            self._unnamed2 = self._io.read_bytes(1)
            self.in_interpolation_type = self._io.read_u1()
            self.out_interpolation_type = self._io.read_u1()
            self.label = KaitaiStream.resolve_enum(Aep.Label, self._io.read_u1())
            self._unnamed6 = self._io.read_bits_int_be(2)
            self.roving = self._io.read_bits_int_be(1) != 0
            self.temporal_auto_bezier = self._io.read_bits_int_be(1) != 0
            self.temporal_continuous = self._io.read_bits_int_be(1) != 0
            self._unnamed10 = self._io.read_bits_int_be(3)
            _on = self.item_type
            if _on == Aep.LdatItemType.color:
                pass
                self.kf_data = Aep.KfColor(self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.marker:
                pass
                self.kf_data = Aep.KfUnknownData(self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.no_value:
                pass
                self.kf_data = Aep.KfNoValue(self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.one_d:
                pass
                self.kf_data = Aep.KfMultiDimensional(1, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.orientation:
                pass
                self.kf_data = Aep.KfMultiDimensional(1, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.three_d:
                pass
                self.kf_data = Aep.KfMultiDimensional(3, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.three_d_spatial:
                pass
                self.kf_data = Aep.KfPosition(3, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.two_d:
                pass
                self.kf_data = Aep.KfMultiDimensional(2, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.two_d_spatial:
                pass
                self.kf_data = Aep.KfPosition(2, self._io, self, self._root)
                self.kf_data._read()
            elif _on == Aep.LdatItemType.unknown:
                pass
                self.kf_data = Aep.KfUnknownData(self._io, self, self._root)
                self.kf_data._read()
            self._dirty = False


        def _fetch_instances(self):
            pass
            _on = self.item_type
            if _on == Aep.LdatItemType.color:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.marker:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.no_value:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.one_d:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.orientation:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.three_d:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.three_d_spatial:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.two_d:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.two_d_spatial:
                pass
                self.kf_data._fetch_instances()
            elif _on == Aep.LdatItemType.unknown:
                pass
                self.kf_data._fetch_instances()


        def _write__seq(self, io=None):
            super(Aep.LdatItem, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_s2be(self.time_raw)
            self._io.write_bytes(self._unnamed2)
            self._io.write_u1(self.in_interpolation_type)
            self._io.write_u1(self.out_interpolation_type)
            self._io.write_u1(int(self.label))
            self._io.write_bits_int_be(2, self._unnamed6)
            self._io.write_bits_int_be(1, int(self.roving))
            self._io.write_bits_int_be(1, int(self.temporal_auto_bezier))
            self._io.write_bits_int_be(1, int(self.temporal_continuous))
            self._io.write_bits_int_be(3, self._unnamed10)
            _on = self.item_type
            if _on == Aep.LdatItemType.color:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.marker:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.no_value:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.one_d:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.orientation:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.three_d:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.three_d_spatial:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.two_d:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.two_d_spatial:
                pass
                self.kf_data._write__seq(self._io)
            elif _on == Aep.LdatItemType.unknown:
                pass
                self.kf_data._write__seq(self._io)


        def _check(self):
            if len(self._unnamed0) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 1, len(self._unnamed0))
            if len(self._unnamed2) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 1, len(self._unnamed2))
            _on = self.item_type
            if _on == Aep.LdatItemType.color:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
            elif _on == Aep.LdatItemType.marker:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
            elif _on == Aep.LdatItemType.no_value:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
            elif _on == Aep.LdatItemType.one_d:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 1:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 1, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.orientation:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 1:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 1, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.three_d:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 3:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 3, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.three_d_spatial:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 3:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 3, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.two_d:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 2:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 2, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.two_d_spatial:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
                if self.kf_data.num_value != 2:
                    raise kaitaistruct.ConsistencyError(u"kf_data", 2, self.kf_data.num_value)
            elif _on == Aep.LdatItemType.unknown:
                pass
                if self.kf_data._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self._root, self.kf_data._root)
                if self.kf_data._parent != self:
                    raise kaitaistruct.ConsistencyError(u"kf_data", self, self.kf_data._parent)
            self._dirty = False


    class LdtaBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.LdtaBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.layer_id = self._io.read_u4be()
            self.quality = self._io.read_u2be()
            self._unnamed2 = self._io.read_bytes(2)
            self.stretch_dividend = self._io.read_s4be()
            self.start_time_dividend = self._io.read_s4be()
            self.start_time_divisor = self._io.read_u4be()
            self.in_point_dividend = self._io.read_s4be()
            self.in_point_divisor = self._io.read_u4be()
            self.out_point_dividend = self._io.read_s4be()
            self.out_point_divisor = self._io.read_u4be()
            self._unnamed10 = self._io.read_bytes(1)
            self._unnamed11 = self._io.read_bits_int_be(1) != 0
            self.sampling_quality = self._io.read_bits_int_be(1) != 0
            self.environment_layer = self._io.read_bits_int_be(1) != 0
            self.characters_toward_camera = self._io.read_bits_int_be(1) != 0
            self.three_d_per_char = self._io.read_bits_int_be(1) != 0
            self.frame_blending_mode = self._io.read_bits_int_be(1) != 0
            self.guide_layer = self._io.read_bits_int_be(1) != 0
            self._unnamed18 = self._io.read_bits_int_be(1) != 0
            self.null_layer = self._io.read_bits_int_be(1) != 0
            self._unnamed20 = self._io.read_bits_int_be(1) != 0
            self.camera_or_poi_auto_orient = self._io.read_bits_int_be(1) != 0
            self.markers_locked = self._io.read_bits_int_be(1) != 0
            self.solo = self._io.read_bits_int_be(1) != 0
            self.three_d_layer = self._io.read_bits_int_be(1) != 0
            self.adjustment_layer = self._io.read_bits_int_be(1) != 0
            self.auto_orient_along_path = self._io.read_bits_int_be(1) != 0
            self.collapse_transformation = self._io.read_bits_int_be(1) != 0
            self.shy = self._io.read_bits_int_be(1) != 0
            self.locked = self._io.read_bits_int_be(1) != 0
            self.frame_blending = self._io.read_bits_int_be(1) != 0
            self.motion_blur = self._io.read_bits_int_be(1) != 0
            self.effects_active = self._io.read_bits_int_be(1) != 0
            self.audio_enabled = self._io.read_bits_int_be(1) != 0
            self.enabled = self._io.read_bits_int_be(1) != 0
            self.source_id = self._io.read_u4be()
            self._unnamed36 = self._io.read_bytes(17)
            self.label = KaitaiStream.resolve_enum(Aep.Label, self._io.read_u1())
            self._unnamed38 = self._io.read_bytes(2)
            self.layer_name = (self._io.read_bytes(32)).decode(u"windows-1252")
            self._unnamed40 = self._io.read_bytes(3)
            self.blending_mode = self._io.read_u1()
            self._unnamed42 = self._io.read_bytes(3)
            self.preserve_transparency = self._io.read_u1()
            self._unnamed44 = self._io.read_bytes(3)
            self.track_matte_type = self._io.read_u1()
            self.stretch_divisor = self._io.read_u4be()
            self._unnamed47 = self._io.read_bytes(19)
            self.layer_type = KaitaiStream.resolve_enum(Aep.LayerType, self._io.read_u1())
            self.parent_id = self._io.read_u4be()
            self._unnamed50 = self._io.read_bytes(3)
            self.light_type = self._io.read_u1()
            self._unnamed52 = self._io.read_bytes(20)
            if self._io.size() - self._io.pos() >= 4:
                pass
                self.matte_layer_id = self._io.read_u4be()

            self._dirty = False


        def _fetch_instances(self):
            pass
            if self._io.size() - self._io.pos() >= 4:
                pass



        def _write__seq(self, io=None):
            super(Aep.LdtaBody, self)._write__seq(io)
            self._io.write_u4be(self.layer_id)
            self._io.write_u2be(self.quality)
            self._io.write_bytes(self._unnamed2)
            self._io.write_s4be(self.stretch_dividend)
            self._io.write_s4be(self.start_time_dividend)
            self._io.write_u4be(self.start_time_divisor)
            self._io.write_s4be(self.in_point_dividend)
            self._io.write_u4be(self.in_point_divisor)
            self._io.write_s4be(self.out_point_dividend)
            self._io.write_u4be(self.out_point_divisor)
            self._io.write_bytes(self._unnamed10)
            self._io.write_bits_int_be(1, int(self._unnamed11))
            self._io.write_bits_int_be(1, int(self.sampling_quality))
            self._io.write_bits_int_be(1, int(self.environment_layer))
            self._io.write_bits_int_be(1, int(self.characters_toward_camera))
            self._io.write_bits_int_be(1, int(self.three_d_per_char))
            self._io.write_bits_int_be(1, int(self.frame_blending_mode))
            self._io.write_bits_int_be(1, int(self.guide_layer))
            self._io.write_bits_int_be(1, int(self._unnamed18))
            self._io.write_bits_int_be(1, int(self.null_layer))
            self._io.write_bits_int_be(1, int(self._unnamed20))
            self._io.write_bits_int_be(1, int(self.camera_or_poi_auto_orient))
            self._io.write_bits_int_be(1, int(self.markers_locked))
            self._io.write_bits_int_be(1, int(self.solo))
            self._io.write_bits_int_be(1, int(self.three_d_layer))
            self._io.write_bits_int_be(1, int(self.adjustment_layer))
            self._io.write_bits_int_be(1, int(self.auto_orient_along_path))
            self._io.write_bits_int_be(1, int(self.collapse_transformation))
            self._io.write_bits_int_be(1, int(self.shy))
            self._io.write_bits_int_be(1, int(self.locked))
            self._io.write_bits_int_be(1, int(self.frame_blending))
            self._io.write_bits_int_be(1, int(self.motion_blur))
            self._io.write_bits_int_be(1, int(self.effects_active))
            self._io.write_bits_int_be(1, int(self.audio_enabled))
            self._io.write_bits_int_be(1, int(self.enabled))
            self._io.write_u4be(self.source_id)
            self._io.write_bytes(self._unnamed36)
            self._io.write_u1(int(self.label))
            self._io.write_bytes(self._unnamed38)
            self._io.write_bytes((self.layer_name).encode(u"windows-1252"))
            self._io.write_bytes(self._unnamed40)
            self._io.write_u1(self.blending_mode)
            self._io.write_bytes(self._unnamed42)
            self._io.write_u1(self.preserve_transparency)
            self._io.write_bytes(self._unnamed44)
            self._io.write_u1(self.track_matte_type)
            self._io.write_u4be(self.stretch_divisor)
            self._io.write_bytes(self._unnamed47)
            self._io.write_u1(int(self.layer_type))
            self._io.write_u4be(self.parent_id)
            self._io.write_bytes(self._unnamed50)
            self._io.write_u1(self.light_type)
            self._io.write_bytes(self._unnamed52)
            if self._io.size() - self._io.pos() >= 4:
                pass
                self._io.write_u4be(self.matte_layer_id)



        def _check(self):
            if len(self._unnamed2) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 2, len(self._unnamed2))
            if len(self._unnamed10) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed10", 1, len(self._unnamed10))
            if len(self._unnamed36) != 17:
                raise kaitaistruct.ConsistencyError(u"_unnamed36", 17, len(self._unnamed36))
            if len(self._unnamed38) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed38", 2, len(self._unnamed38))
            if len((self.layer_name).encode(u"windows-1252")) != 32:
                raise kaitaistruct.ConsistencyError(u"layer_name", 32, len((self.layer_name).encode(u"windows-1252")))
            if len(self._unnamed40) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed40", 3, len(self._unnamed40))
            if len(self._unnamed42) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed42", 3, len(self._unnamed42))
            if len(self._unnamed44) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed44", 3, len(self._unnamed44))
            if len(self._unnamed47) != 19:
                raise kaitaistruct.ConsistencyError(u"_unnamed47", 19, len(self._unnamed47))
            if len(self._unnamed50) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed50", 3, len(self._unnamed50))
            if len(self._unnamed52) != 20:
                raise kaitaistruct.ConsistencyError(u"_unnamed52", 20, len(self._unnamed52))
            self._dirty = False

        @property
        def auto_orient_type(self):
            """Computed auto-orient mode from individual binary flags.
            0=no_auto_orient, 1=along_path, 2=camera_or_point_of_interest,
            3=characters_toward_camera.
            """
            if hasattr(self, '_m_auto_orient_type'):
                return self._m_auto_orient_type

            self._m_auto_orient_type = KaitaiStream.resolve_enum(Aep.AutoOrientType, (1 if self.auto_orient_along_path else (2 if  ((self.camera_or_poi_auto_orient) and (self.three_d_layer))  else (3 if  ((self.characters_toward_camera) and (self.three_d_per_char))  else 0))))
            return getattr(self, '_m_auto_orient_type', None)

        def _invalidate_auto_orient_type(self):
            del self._m_auto_orient_type
        @property
        def frame_blending_type(self):
            """Computed frame blending mode from frame_blending (enabled) and
            frame_blending_mode (0=frame_mix, 1=pixel_motion) bits.
            0=no_frame_blend, 1=frame_mix, 2=pixel_motion.
            """
            if hasattr(self, '_m_frame_blending_type'):
                return self._m_frame_blending_type

            self._m_frame_blending_type = KaitaiStream.resolve_enum(Aep.FrameBlendingType, ((2 if self.frame_blending_mode else 1) if self.frame_blending else 0))
            return getattr(self, '_m_frame_blending_type', None)

        def _invalidate_frame_blending_type(self):
            del self._m_frame_blending_type
        @property
        def in_point(self):
            """In point relative to start_time (seconds, before stretch)."""
            if hasattr(self, '_m_in_point'):
                return self._m_in_point

            self._m_in_point = (self.in_point_dividend * 1.0) / self.in_point_divisor
            return getattr(self, '_m_in_point', None)

        def _invalidate_in_point(self):
            del self._m_in_point
        @property
        def out_point(self):
            """Out point relative to start_time (seconds, before stretch)."""
            if hasattr(self, '_m_out_point'):
                return self._m_out_point

            self._m_out_point = (self.out_point_dividend * 1.0) / self.out_point_divisor
            return getattr(self, '_m_out_point', None)

        def _invalidate_out_point(self):
            del self._m_out_point
        @property
        def start_time(self):
            if hasattr(self, '_m_start_time'):
                return self._m_start_time

            self._m_start_time = (self.start_time_dividend * 1.0) / self.start_time_divisor
            return getattr(self, '_m_start_time', None)

        def _invalidate_start_time(self):
            del self._m_start_time
        @property
        def stretch(self):
            """Layer time stretch as percentage (100 = normal speed)."""
            if hasattr(self, '_m_stretch'):
                return self._m_stretch

            self._m_stretch = ((self.stretch_dividend * 100.0) / self.stretch_divisor if self.stretch_divisor != 0 else 0)
            return getattr(self, '_m_stretch', None)

        def _invalidate_stretch(self):
            del self._m_stretch

    class Lhd3Body(ReadWriteKaitaiStruct):
        """Header for item/keyframe lists. AE reuses this structure for:
        - Property keyframes (count = keyframe count, item_size = keyframe data size)
        - Render queue items (count = item count, item_size = 2246 for settings)
        - Output module items (count = item count, item_size = 128 for settings)
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Lhd3Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(10)
            self.count = self._io.read_u2be()
            self._unnamed2 = self._io.read_bytes(6)
            self.item_size = self._io.read_u2be()
            self._unnamed4 = self._io.read_bytes(3)
            self.item_type_raw = self._io.read_u1()
            self._unnamed6 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.Lhd3Body, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u2be(self.count)
            self._io.write_bytes(self._unnamed2)
            self._io.write_u2be(self.item_size)
            self._io.write_bytes(self._unnamed4)
            self._io.write_u1(self.item_type_raw)
            self._io.write_bytes(self._unnamed6)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 10:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 10, len(self._unnamed0))
            if len(self._unnamed2) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 6, len(self._unnamed2))
            if len(self._unnamed4) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 3, len(self._unnamed4))
            self._dirty = False

        @property
        def item_type(self):
            if hasattr(self, '_m_item_type'):
                return self._m_item_type

            self._m_item_type = (Aep.LdatItemType.lrdr if  ((self.item_type_raw == 1) and (self.item_size == 2246))  else (Aep.LdatItemType.litm if  ((self.item_type_raw == 1) and (self.item_size == 128))  else (Aep.LdatItemType.gide if  ((self.item_type_raw == 2) and (self.item_size == 16))  else (Aep.LdatItemType.color if  ((self.item_type_raw == 4) and (self.item_size == 152))  else (Aep.LdatItemType.three_d if  ((self.item_type_raw == 4) and (self.item_size == 128))  else (Aep.LdatItemType.two_d_spatial if  ((self.item_type_raw == 4) and (self.item_size == 104))  else (Aep.LdatItemType.two_d if  ((self.item_type_raw == 4) and (self.item_size == 88))  else (Aep.LdatItemType.orientation if  ((self.item_type_raw == 4) and (self.item_size == 80))  else (Aep.LdatItemType.no_value if  ((self.item_type_raw == 4) and (self.item_size == 64))  else (Aep.LdatItemType.one_d if  ((self.item_type_raw == 4) and (self.item_size == 48))  else (Aep.LdatItemType.marker if  ((self.item_type_raw == 4) and (self.item_size == 16))  else (Aep.LdatItemType.shape if  ((self.item_type_raw == 4) and (self.item_size == 8))  else Aep.LdatItemType.unknown))))))))))))
            return getattr(self, '_m_item_type', None)

        def _invalidate_item_type(self):
            del self._m_item_type

    class LinlBody(ReadWriteKaitaiStruct):
        """Interpret As Linear Light setting for footage color management.
        Inside LIST:CLRS in a footage item's LIST:Pin.
        Controls whether footage is treated as having linear gamma.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.LinlBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.value = self._io.read_u1()
            self._unnamed1 = self._io.read_bytes(3)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.LinlBody, self)._write__seq(io)
            self._io.write_u1(self.value)
            self._io.write_bytes(self._unnamed1)


        def _check(self):
            if len(self._unnamed1) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 3, len(self._unnamed1))
            self._dirty = False


    class ListBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.ListBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.list_type = (self._io.read_bytes(4)).decode(u"windows-1252")
            if self.list_type != u"btdk":
                pass
                self.chunks = []
                i = 0
                while not self._io.is_eof():
                    _t_chunks = Aep.Chunk(self._io, self, self._root)
                    try:
                        _t_chunks._read()
                    finally:
                        self.chunks.append(_t_chunks)
                    i += 1


            if self.list_type == u"btdk":
                pass
                self.binary_data = self._io.read_bytes_full()

            self._dirty = False


        def _fetch_instances(self):
            pass
            if self.list_type != u"btdk":
                pass
                for i in range(len(self.chunks)):
                    pass
                    self.chunks[i]._fetch_instances()


            if self.list_type == u"btdk":
                pass



        def _write__seq(self, io=None):
            super(Aep.ListBody, self)._write__seq(io)
            self._io.write_bytes((self.list_type).encode(u"windows-1252"))
            if self.list_type != u"btdk":
                pass
                for i in range(len(self.chunks)):
                    pass
                    if self._io.is_eof():
                        raise kaitaistruct.ConsistencyError(u"chunks", 0, self._io.size() - self._io.pos())
                    self.chunks[i]._write__seq(self._io)

                if not self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"chunks", 0, self._io.size() - self._io.pos())

            if self.list_type == u"btdk":
                pass
                self._io.write_bytes(self.binary_data)
                if not self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"binary_data", 0, self._io.size() - self._io.pos())



        def _check(self):
            if len((self.list_type).encode(u"windows-1252")) != 4:
                raise kaitaistruct.ConsistencyError(u"list_type", 4, len((self.list_type).encode(u"windows-1252")))
            if self.list_type != u"btdk":
                pass
                for i in range(len(self.chunks)):
                    pass
                    if self.chunks[i]._root != self._root:
                        raise kaitaistruct.ConsistencyError(u"chunks", self._root, self.chunks[i]._root)
                    if self.chunks[i]._parent != self:
                        raise kaitaistruct.ConsistencyError(u"chunks", self, self.chunks[i]._parent)


            if self.list_type == u"btdk":
                pass

            self._dirty = False

        @property
        def ldat(self):
            """Data chunk (keyframe / shape binary items). Absent when property has no keyframes."""
            if hasattr(self, '_m_ldat'):
                return self._m_ldat

            if  ((self.list_type == u"list") and (len(self.chunks) >= 2)) :
                pass
                self._m_ldat = self.chunks[1]

            return getattr(self, '_m_ldat', None)

        def _invalidate_ldat(self):
            del self._m_ldat
        @property
        def lhd3(self):
            """Header chunk (count + item size). Always the first child."""
            if hasattr(self, '_m_lhd3'):
                return self._m_lhd3

            if self.list_type == u"list":
                pass
                self._m_lhd3 = self.chunks[0]

            return getattr(self, '_m_lhd3', None)

        def _invalidate_lhd3(self):
            del self._m_lhd3
        @property
        def tdb4(self):
            """Property metadata chunk. Always the third child."""
            if hasattr(self, '_m_tdb4'):
                return self._m_tdb4

            if self.list_type == u"tdbs":
                pass
                self._m_tdb4 = self.chunks[2]

            return getattr(self, '_m_tdb4', None)

        def _invalidate_tdb4(self):
            del self._m_tdb4
        @property
        def tdsb(self):
            """Property flags chunk. Always the first child."""
            if hasattr(self, '_m_tdsb'):
                return self._m_tdsb

            if self.list_type == u"tdbs":
                pass
                self._m_tdsb = self.chunks[0]

            return getattr(self, '_m_tdsb', None)

        def _invalidate_tdsb(self):
            del self._m_tdsb
        @property
        def tdsn(self):
            """Property name chunk (tdsn wraps a Utf8 child). Always the second child."""
            if hasattr(self, '_m_tdsn'):
                return self._m_tdsn

            if self.list_type == u"tdbs":
                pass
                self._m_tdsn = self.chunks[1]

            return getattr(self, '_m_tdsn', None)

        def _invalidate_tdsn(self):
            del self._m_tdsn

    class LnrbBody(ReadWriteKaitaiStruct):
        """Linear blending flag. Presence of this chunk in the root chunk list
        means linear blending is enabled for the project.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.LnrbBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(1)
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, self._io, u"/types/lnrb_body/seq/0")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.LnrbBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)


        def _check(self):
            if len(self._unnamed0) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 1, len(self._unnamed0))
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, None, u"/types/lnrb_body/seq/0")
            self._dirty = False


    class LnrpBody(ReadWriteKaitaiStruct):
        """Linearize working space flag. Presence of this chunk in the root
        chunk list means the working color space is linearized.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.LnrpBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(1)
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, self._io, u"/types/lnrp_body/seq/0")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.LnrpBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)


        def _check(self):
            if len(self._unnamed0) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 1, len(self._unnamed0))
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, None, u"/types/lnrp_body/seq/0")
            self._dirty = False


    class MkifBody(ReadWriteKaitaiStruct):
        """Mask info. Contains inverted flag, locked flag, mask mode,
        motion blur, feather falloff and color.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.MkifBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.inverted = self._io.read_u1()
            self.locked = self._io.read_u1()
            self.mask_motion_blur = self._io.read_u1()
            self.mask_feather_falloff = self._io.read_u1()
            self._unnamed4 = self._io.read_bytes(2)
            self.mode = self._io.read_u2be()
            self._unnamed6 = self._io.read_bytes(37)
            self.color = []
            for i in range(3):
                self.color.append(self._io.read_u1())

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.color)):
                pass



        def _write__seq(self, io=None):
            super(Aep.MkifBody, self)._write__seq(io)
            self._io.write_u1(self.inverted)
            self._io.write_u1(self.locked)
            self._io.write_u1(self.mask_motion_blur)
            self._io.write_u1(self.mask_feather_falloff)
            self._io.write_bytes(self._unnamed4)
            self._io.write_u2be(self.mode)
            self._io.write_bytes(self._unnamed6)
            for i in range(len(self.color)):
                pass
                self._io.write_u1(self.color[i])



        def _check(self):
            if len(self._unnamed4) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 2, len(self._unnamed4))
            if len(self._unnamed6) != 37:
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 37, len(self._unnamed6))
            if len(self.color) != 3:
                raise kaitaistruct.ConsistencyError(u"color", 3, len(self.color))
            for i in range(len(self.color)):
                pass

            self._dirty = False


    class NmhdBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.NmhdBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(3)
            self._unnamed1 = self._io.read_bits_int_be(5)
            self.unknown = self._io.read_bits_int_be(1) != 0
            self.protected_region = self._io.read_bits_int_be(1) != 0
            self.navigation = self._io.read_bits_int_be(1) != 0
            self._unnamed5 = self._io.read_bytes(4)
            self.frame_duration = self._io.read_u4be()
            self._unnamed7 = self._io.read_bytes(4)
            self.label = KaitaiStream.resolve_enum(Aep.Label, self._io.read_u1())
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.NmhdBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(5, self._unnamed1)
            self._io.write_bits_int_be(1, int(self.unknown))
            self._io.write_bits_int_be(1, int(self.protected_region))
            self._io.write_bits_int_be(1, int(self.navigation))
            self._io.write_bytes(self._unnamed5)
            self._io.write_u4be(self.frame_duration)
            self._io.write_bytes(self._unnamed7)
            self._io.write_u1(int(self.label))


        def _check(self):
            if len(self._unnamed0) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 3, len(self._unnamed0))
            if len(self._unnamed5) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed5", 4, len(self._unnamed5))
            if len(self._unnamed7) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 4, len(self._unnamed7))
            self._dirty = False

        @property
        def duration(self):
            """Marker duration in seconds (frame_duration is in 600ths of a second)."""
            if hasattr(self, '_m_duration'):
                return self._m_duration

            self._m_duration = (self.frame_duration * 1.0) / 600
            return getattr(self, '_m_duration', None)

        def _invalidate_duration(self):
            del self._m_duration

    class NnhdBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.NnhdBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(8)
            self.feet_frames_film_type = self._io.read_bits_int_be(1) != 0
            self.time_display_type = self._io.read_bits_int_be(7)
            self.footage_timecode_display_start_type = self._io.read_u1()
            self._unnamed4 = self._io.read_bytes(1)
            self._unnamed5 = self._io.read_bits_int_be(7)
            self.frames_use_feet_frames = self._io.read_bits_int_be(1) != 0
            self._unnamed7 = self._io.read_bytes(2)
            self.timecode_default_base = self._io.read_u2be()
            self._unnamed9 = self._io.read_bytes(4)
            self.frames_count_type = self._io.read_u1()
            self._unnamed11 = self._io.read_bytes(3)
            self.bits_per_channel = self._io.read_u1()
            self.transparency_grid_thumbnails = self._io.read_u1()
            self._unnamed14 = self._io.read_bytes(5)
            self._unnamed15 = self._io.read_bits_int_be(2)
            self.linearize_working_space = self._io.read_bits_int_be(1) != 0
            self._unnamed17 = self._io.read_bits_int_be(5)
            self._unnamed18 = self._io.read_bytes(8)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.NnhdBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(1, int(self.feet_frames_film_type))
            self._io.write_bits_int_be(7, self.time_display_type)
            self._io.write_u1(self.footage_timecode_display_start_type)
            self._io.write_bytes(self._unnamed4)
            self._io.write_bits_int_be(7, self._unnamed5)
            self._io.write_bits_int_be(1, int(self.frames_use_feet_frames))
            self._io.write_bytes(self._unnamed7)
            self._io.write_u2be(self.timecode_default_base)
            self._io.write_bytes(self._unnamed9)
            self._io.write_u1(self.frames_count_type)
            self._io.write_bytes(self._unnamed11)
            self._io.write_u1(self.bits_per_channel)
            self._io.write_u1(self.transparency_grid_thumbnails)
            self._io.write_bytes(self._unnamed14)
            self._io.write_bits_int_be(2, self._unnamed15)
            self._io.write_bits_int_be(1, int(self.linearize_working_space))
            self._io.write_bits_int_be(5, self._unnamed17)
            self._io.write_bytes(self._unnamed18)


        def _check(self):
            if len(self._unnamed0) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 8, len(self._unnamed0))
            if len(self._unnamed4) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 1, len(self._unnamed4))
            if len(self._unnamed7) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 2, len(self._unnamed7))
            if len(self._unnamed9) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed9", 4, len(self._unnamed9))
            if len(self._unnamed11) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 3, len(self._unnamed11))
            if len(self._unnamed14) != 5:
                raise kaitaistruct.ConsistencyError(u"_unnamed14", 5, len(self._unnamed14))
            if len(self._unnamed18) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed18", 8, len(self._unnamed18))
            self._dirty = False

        @property
        def display_start_frame(self):
            """Alternate way of reading the Frame Count setting as 0 or 1."""
            if hasattr(self, '_m_display_start_frame'):
                return self._m_display_start_frame

            self._m_display_start_frame = self.frames_count_type % 2
            return getattr(self, '_m_display_start_frame', None)

        def _invalidate_display_start_frame(self):
            del self._m_display_start_frame

    class OpenexrRoptData(ReadWriteKaitaiStruct):
        """OpenEXR format-specific render options.
        These correspond to the OpenEXR Options dialog in After Effects.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.OpenexrRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(8)
            self._unnamed1 = self._io.read_bytes(2)
            self.compression = self._io.read_u1()
            self.thirty_two_bit_float = self._io.read_u1()
            self.luminance_chroma = self._io.read_u1()
            self._unnamed5 = self._io.read_bytes(1)
            self.dwa_compression_level = self._io.read_f4le()
            self._unnamed7 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.OpenexrRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bytes(self._unnamed1)
            self._io.write_u1(self.compression)
            self._io.write_u1(self.thirty_two_bit_float)
            self._io.write_u1(self.luminance_chroma)
            self._io.write_bytes(self._unnamed5)
            self._io.write_f4le(self.dwa_compression_level)
            self._io.write_bytes(self._unnamed7)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 8, len(self._unnamed0))
            if len(self._unnamed1) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 2, len(self._unnamed1))
            if len(self._unnamed5) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed5", 1, len(self._unnamed5))
            self._dirty = False


    class OptiBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.OptiBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.asset_type = (KaitaiStream.bytes_terminate(self._io.read_bytes(4), 0, False)).decode(u"ASCII")
            self.asset_type_int = self._io.read_u2be()
            if self.asset_type == u"Soli":
                pass
                self._unnamed2 = self._io.read_bytes(8)

            if self.asset_type == u"Soli":
                pass
                self.color = []
                for i in range(3):
                    self.color.append(self._io.read_f4be())


            if self.asset_type == u"Soli":
                pass
                self.solid_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(256), 0, False)).decode(u"windows-1252")

            if self.asset_type_int == 2:
                pass
                self._unnamed5 = self._io.read_bytes(4)

            if self.asset_type_int == 2:
                pass
                self.placeholder_name = (self._io.read_bytes_full()).decode(u"windows-1252")

            if self.asset_type == u"8BPS":
                pass
                self._unnamed7 = self._io.read_bytes(10)

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_index = self._io.read_u2be()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed9 = self._io.read_bytes(4)

            if self.asset_type == u"8BPS":
                pass
                self._unnamed10 = self._io.read_bytes(4)

            if self.asset_type == u"8BPS":
                pass
                self._unnamed11 = self._io.read_bytes(4)

            if self.asset_type == u"8BPS":
                pass
                self.psd_channels = self._io.read_u1()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed13 = self._io.read_bytes(1)

            if self.asset_type == u"8BPS":
                pass
                self.psd_canvas_height = self._io.read_u2le()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed15 = self._io.read_bytes(2)

            if self.asset_type == u"8BPS":
                pass
                self.psd_canvas_width = self._io.read_u2le()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed17 = self._io.read_bytes(2)

            if self.asset_type == u"8BPS":
                pass
                self.psd_bit_depth = self._io.read_u1()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed19 = self._io.read_bytes(7)

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_count = self._io.read_u1()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed21 = self._io.read_bytes(29)

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_top = self._io.read_s4le()

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_left = self._io.read_s4le()

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_bottom = self._io.read_s4le()

            if self.asset_type == u"8BPS":
                pass
                self.psd_layer_right = self._io.read_s4le()

            if self.asset_type == u"8BPS":
                pass
                self._unnamed26 = self._io.read_bytes(250)

            if self.asset_type == u"8BPS":
                pass
                self.psd_group_name = (self._io.read_bytes_full()).decode(u"UTF-8")

            self._unnamed28 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass
            if self.asset_type == u"Soli":
                pass

            if self.asset_type == u"Soli":
                pass
                for i in range(len(self.color)):
                    pass


            if self.asset_type == u"Soli":
                pass

            if self.asset_type_int == 2:
                pass

            if self.asset_type_int == 2:
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass



        def _write__seq(self, io=None):
            super(Aep.OptiBody, self)._write__seq(io)
            self._io.write_bytes_limit((self.asset_type).encode(u"ASCII"), 4, 0, 0)
            self._io.write_u2be(self.asset_type_int)
            if self.asset_type == u"Soli":
                pass
                self._io.write_bytes(self._unnamed2)

            if self.asset_type == u"Soli":
                pass
                for i in range(len(self.color)):
                    pass
                    self._io.write_f4be(self.color[i])


            if self.asset_type == u"Soli":
                pass
                self._io.write_bytes_limit((self.solid_name).encode(u"windows-1252"), 256, 0, 0)

            if self.asset_type_int == 2:
                pass
                self._io.write_bytes(self._unnamed5)

            if self.asset_type_int == 2:
                pass
                self._io.write_bytes((self.placeholder_name).encode(u"windows-1252"))
                if not self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"placeholder_name", 0, self._io.size() - self._io.pos())

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed7)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u2be(self.psd_layer_index)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed9)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed10)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed11)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u1(self.psd_channels)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed13)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u2le(self.psd_canvas_height)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed15)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u2le(self.psd_canvas_width)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed17)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u1(self.psd_bit_depth)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed19)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_u1(self.psd_layer_count)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed21)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_s4le(self.psd_layer_top)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_s4le(self.psd_layer_left)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_s4le(self.psd_layer_bottom)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_s4le(self.psd_layer_right)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes(self._unnamed26)

            if self.asset_type == u"8BPS":
                pass
                self._io.write_bytes((self.psd_group_name).encode(u"UTF-8"))
                if not self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"psd_group_name", 0, self._io.size() - self._io.pos())

            self._io.write_bytes(self._unnamed28)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed28", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len((self.asset_type).encode(u"ASCII")) > 4:
                raise kaitaistruct.ConsistencyError(u"asset_type", 4, len((self.asset_type).encode(u"ASCII")))
            if KaitaiStream.byte_array_index_of((self.asset_type).encode(u"ASCII"), 0) != -1:
                raise kaitaistruct.ConsistencyError(u"asset_type", -1, KaitaiStream.byte_array_index_of((self.asset_type).encode(u"ASCII"), 0))
            if self.asset_type == u"Soli":
                pass
                if len(self._unnamed2) != 8:
                    raise kaitaistruct.ConsistencyError(u"_unnamed2", 8, len(self._unnamed2))

            if self.asset_type == u"Soli":
                pass
                if len(self.color) != 3:
                    raise kaitaistruct.ConsistencyError(u"color", 3, len(self.color))
                for i in range(len(self.color)):
                    pass


            if self.asset_type == u"Soli":
                pass
                if len((self.solid_name).encode(u"windows-1252")) > 256:
                    raise kaitaistruct.ConsistencyError(u"solid_name", 256, len((self.solid_name).encode(u"windows-1252")))
                if KaitaiStream.byte_array_index_of((self.solid_name).encode(u"windows-1252"), 0) != -1:
                    raise kaitaistruct.ConsistencyError(u"solid_name", -1, KaitaiStream.byte_array_index_of((self.solid_name).encode(u"windows-1252"), 0))

            if self.asset_type_int == 2:
                pass
                if len(self._unnamed5) != 4:
                    raise kaitaistruct.ConsistencyError(u"_unnamed5", 4, len(self._unnamed5))

            if self.asset_type_int == 2:
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed7) != 10:
                    raise kaitaistruct.ConsistencyError(u"_unnamed7", 10, len(self._unnamed7))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed9) != 4:
                    raise kaitaistruct.ConsistencyError(u"_unnamed9", 4, len(self._unnamed9))

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed10) != 4:
                    raise kaitaistruct.ConsistencyError(u"_unnamed10", 4, len(self._unnamed10))

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed11) != 4:
                    raise kaitaistruct.ConsistencyError(u"_unnamed11", 4, len(self._unnamed11))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed13) != 1:
                    raise kaitaistruct.ConsistencyError(u"_unnamed13", 1, len(self._unnamed13))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed15) != 2:
                    raise kaitaistruct.ConsistencyError(u"_unnamed15", 2, len(self._unnamed15))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed17) != 2:
                    raise kaitaistruct.ConsistencyError(u"_unnamed17", 2, len(self._unnamed17))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed19) != 7:
                    raise kaitaistruct.ConsistencyError(u"_unnamed19", 7, len(self._unnamed19))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed21) != 29:
                    raise kaitaistruct.ConsistencyError(u"_unnamed21", 29, len(self._unnamed21))

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass

            if self.asset_type == u"8BPS":
                pass
                if len(self._unnamed26) != 250:
                    raise kaitaistruct.ConsistencyError(u"_unnamed26", 250, len(self._unnamed26))

            if self.asset_type == u"8BPS":
                pass

            self._dirty = False


    class OtlnBody(ReadWriteKaitaiStruct):
        """Comp panel outline entries inside LIST FEE (composition timeline).
        Each entry is 4 bytes. The first byte contains flags:
          - bit 7 (0x80): collapsed in the timeline
          - bit 6 (0x40): selected
        Entries correspond 1:1 to layers and their property-tree nodes
        in DFS order across all visible layers of the active composition.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.OtlnBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.num_entries = self._io.read_u4be()
            self.entries = []
            for i in range(self.num_entries):
                _t_entries = Aep.OtlnEntry(self._io, self, self._root)
                try:
                    _t_entries._read()
                finally:
                    self.entries.append(_t_entries)

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.entries)):
                pass
                self.entries[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.OtlnBody, self)._write__seq(io)
            self._io.write_u4be(self.num_entries)
            for i in range(len(self.entries)):
                pass
                self.entries[i]._write__seq(self._io)



        def _check(self):
            if len(self.entries) != self.num_entries:
                raise kaitaistruct.ConsistencyError(u"entries", self.num_entries, len(self.entries))
            for i in range(len(self.entries)):
                pass
                if self.entries[i]._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"entries", self._root, self.entries[i]._root)
                if self.entries[i]._parent != self:
                    raise kaitaistruct.ConsistencyError(u"entries", self, self.entries[i]._parent)

            self._dirty = False


    class OtlnEntry(ReadWriteKaitaiStruct):
        """Single comp panel outline entry."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.OtlnEntry, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.collapsed = self._io.read_bits_int_be(1) != 0
            self.selected = self._io.read_bits_int_be(1) != 0
            self.is_property = self._io.read_bits_int_be(1) != 0
            self._unnamed3 = self._io.read_bits_int_be(1) != 0
            self.is_sub_entry = self._io.read_bits_int_be(1) != 0
            self._unnamed5 = self._io.read_bits_int_be(3)
            self._unnamed6 = self._io.read_bytes(2)
            self.entry_type = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.OtlnEntry, self)._write__seq(io)
            self._io.write_bits_int_be(1, int(self.collapsed))
            self._io.write_bits_int_be(1, int(self.selected))
            self._io.write_bits_int_be(1, int(self.is_property))
            self._io.write_bits_int_be(1, int(self._unnamed3))
            self._io.write_bits_int_be(1, int(self.is_sub_entry))
            self._io.write_bits_int_be(3, self._unnamed5)
            self._io.write_bytes(self._unnamed6)
            self._io.write_u1(self.entry_type)


        def _check(self):
            if len(self._unnamed6) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 2, len(self._unnamed6))
            self._dirty = False

        @property
        def is_layer_marker(self):
            """When true, this entry is a per-layer boundary marker."""
            if hasattr(self, '_m_is_layer_marker'):
                return self._m_is_layer_marker

            self._m_is_layer_marker = self.entry_type == 68
            return getattr(self, '_m_is_layer_marker', None)

        def _invalidate_is_layer_marker(self):
            del self._m_is_layer_marker

    class OutputModuleSettingsLdatBody(ReadWriteKaitaiStruct):
        """Per-output-module settings chunk (128 bytes).
        Used under LIST:list within LIST:LItm for each render queue item.
        Note: The actual comp_id is stored in render_settings_ldat_body, not here.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.OutputModuleSettingsLdatBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(7)
            self.preserve_rgb = self._io.read_bits_int_be(1) != 0
            self.include_source_xmp = self._io.read_bits_int_be(1) != 0
            self._unnamed3 = self._io.read_bits_int_be(1) != 0
            self.use_region_of_interest = self._io.read_bits_int_be(1) != 0
            self.use_comp_frame_number = self._io.read_bits_int_be(1) != 0
            self._unnamed6 = self._io.read_bits_int_be(3)
            self.post_render_target_comp_id = self._io.read_u4be()
            self._unnamed8 = self._io.read_bytes(4)
            self._unnamed9 = self._io.read_bytes(3)
            self.channels = self._io.read_u1()
            self._unnamed11 = self._io.read_bytes(3)
            self.resize_quality = self._io.read_u1()
            self._unnamed13 = self._io.read_bytes(3)
            self.resize = self._io.read_u1()
            self._unnamed15 = self._io.read_bytes(1)
            self.lock_aspect_ratio = self._io.read_u1()
            self._unnamed17 = self._io.read_bytes(1)
            self._unnamed18 = self._io.read_bits_int_be(7)
            self.crop = self._io.read_bits_int_be(1) != 0
            self.crop_top = self._io.read_u2be()
            self.crop_left = self._io.read_u2be()
            self.crop_bottom = self._io.read_u2be()
            self.crop_right = self._io.read_u2be()
            self._unnamed24 = self._io.read_bytes(2)
            self.output_audio = self._io.read_u1()
            self._unnamed26 = self._io.read_bytes(4)
            self.include_project_link = self._io.read_u1()
            self.post_render_action = self._io.read_u4be()
            self.post_render_use_comp = self._io.read_u4be()
            self._unnamed30 = self._io.read_bytes(16)
            self.output_profile_id = self._io.read_bytes(16)
            self._unnamed32 = self._io.read_bytes(3)
            self.convert_to_linear_light = self._io.read_u1()
            self._unnamed34 = self._io.read_bytes(1)
            self.output_color_space_working = self._io.read_u1()
            self._unnamed36 = self._io.read_bytes(34)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.OutputModuleSettingsLdatBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(1, int(self.preserve_rgb))
            self._io.write_bits_int_be(1, int(self.include_source_xmp))
            self._io.write_bits_int_be(1, int(self._unnamed3))
            self._io.write_bits_int_be(1, int(self.use_region_of_interest))
            self._io.write_bits_int_be(1, int(self.use_comp_frame_number))
            self._io.write_bits_int_be(3, self._unnamed6)
            self._io.write_u4be(self.post_render_target_comp_id)
            self._io.write_bytes(self._unnamed8)
            self._io.write_bytes(self._unnamed9)
            self._io.write_u1(self.channels)
            self._io.write_bytes(self._unnamed11)
            self._io.write_u1(self.resize_quality)
            self._io.write_bytes(self._unnamed13)
            self._io.write_u1(self.resize)
            self._io.write_bytes(self._unnamed15)
            self._io.write_u1(self.lock_aspect_ratio)
            self._io.write_bytes(self._unnamed17)
            self._io.write_bits_int_be(7, self._unnamed18)
            self._io.write_bits_int_be(1, int(self.crop))
            self._io.write_u2be(self.crop_top)
            self._io.write_u2be(self.crop_left)
            self._io.write_u2be(self.crop_bottom)
            self._io.write_u2be(self.crop_right)
            self._io.write_bytes(self._unnamed24)
            self._io.write_u1(self.output_audio)
            self._io.write_bytes(self._unnamed26)
            self._io.write_u1(self.include_project_link)
            self._io.write_u4be(self.post_render_action)
            self._io.write_u4be(self.post_render_use_comp)
            self._io.write_bytes(self._unnamed30)
            self._io.write_bytes(self.output_profile_id)
            self._io.write_bytes(self._unnamed32)
            self._io.write_u1(self.convert_to_linear_light)
            self._io.write_bytes(self._unnamed34)
            self._io.write_u1(self.output_color_space_working)
            self._io.write_bytes(self._unnamed36)


        def _check(self):
            if len(self._unnamed0) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 7, len(self._unnamed0))
            if len(self._unnamed8) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed8", 4, len(self._unnamed8))
            if len(self._unnamed9) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed9", 3, len(self._unnamed9))
            if len(self._unnamed11) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 3, len(self._unnamed11))
            if len(self._unnamed13) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed13", 3, len(self._unnamed13))
            if len(self._unnamed15) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed15", 1, len(self._unnamed15))
            if len(self._unnamed17) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed17", 1, len(self._unnamed17))
            if len(self._unnamed24) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed24", 2, len(self._unnamed24))
            if len(self._unnamed26) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed26", 4, len(self._unnamed26))
            if len(self._unnamed30) != 16:
                raise kaitaistruct.ConsistencyError(u"_unnamed30", 16, len(self._unnamed30))
            if len(self.output_profile_id) != 16:
                raise kaitaistruct.ConsistencyError(u"output_profile_id", 16, len(self.output_profile_id))
            if len(self._unnamed32) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed32", 3, len(self._unnamed32))
            if len(self._unnamed34) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed34", 1, len(self._unnamed34))
            if len(self._unnamed36) != 34:
                raise kaitaistruct.ConsistencyError(u"_unnamed36", 34, len(self._unnamed36))
            self._dirty = False


    class PardBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.PardBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(15)
            self.property_control_type = KaitaiStream.resolve_enum(Aep.PropertyControlType, self._io.read_u1())
            self.name = (self._io.read_bytes(32)).decode(u"windows-1252")
            self._unnamed3 = self._io.read_bytes(8)
            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                self.last_color = []
                for i in range(4):
                    self.last_color.append(self._io.read_u1())


            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                self.default_color = []
                for i in range(4):
                    self.default_color.append(self._io.read_u1())


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.angle) or (self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.angle:
                    pass
                    self.last_value = self._io.read_s4be()
                elif _on == Aep.PropertyControlType.boolean:
                    pass
                    self.last_value = self._io.read_u4be()
                elif _on == Aep.PropertyControlType.enum:
                    pass
                    self.last_value = self._io.read_u4be()
                elif _on == Aep.PropertyControlType.scalar:
                    pass
                    self.last_value = self._io.read_s4be()
                elif _on == Aep.PropertyControlType.slider:
                    pass
                    self.last_value = self._io.read_f8be()

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                    self.last_value_x_raw = self._io.read_f8be()
                elif _on == Aep.PropertyControlType.two_d:
                    pass
                    self.last_value_x_raw = self._io.read_s4be()

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                    self.last_value_y_raw = self._io.read_f8be()
                elif _on == Aep.PropertyControlType.two_d:
                    pass
                    self.last_value_y_raw = self._io.read_s4be()

            if self.property_control_type == Aep.PropertyControlType.three_d:
                pass
                self.last_value_z_raw = self._io.read_f8be()

            if self.property_control_type == Aep.PropertyControlType.enum:
                pass
                self.nb_options = self._io.read_s4be()

            if  ((self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.boolean:
                    pass
                    self.default = self._io.read_u1()
                elif _on == Aep.PropertyControlType.enum:
                    pass
                    self.default = self._io.read_s4be()

            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.color) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                self._unnamed12 = self._io.read_bytes((72 if self.property_control_type == Aep.PropertyControlType.scalar else (64 if self.property_control_type == Aep.PropertyControlType.color else 52)))

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass
                self.min_value = self._io.read_s2be()

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass
                self._unnamed14 = self._io.read_bytes(2)

            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                self.max_color = []
                for i in range(4):
                    self.max_color.append(self._io.read_u1())


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.scalar:
                    pass
                    self.max_value = self._io.read_s2be()
                elif _on == Aep.PropertyControlType.slider:
                    pass
                    self.max_value = self._io.read_f4be()

            self._unnamed17 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass
            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.last_color)):
                    pass


            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.default_color)):
                    pass


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.angle) or (self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.angle:
                    pass
                elif _on == Aep.PropertyControlType.boolean:
                    pass
                elif _on == Aep.PropertyControlType.enum:
                    pass
                elif _on == Aep.PropertyControlType.scalar:
                    pass
                elif _on == Aep.PropertyControlType.slider:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                elif _on == Aep.PropertyControlType.two_d:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                elif _on == Aep.PropertyControlType.two_d:
                    pass

            if self.property_control_type == Aep.PropertyControlType.three_d:
                pass

            if self.property_control_type == Aep.PropertyControlType.enum:
                pass

            if  ((self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.boolean:
                    pass
                elif _on == Aep.PropertyControlType.enum:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.color) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass

            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.max_color)):
                    pass


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.scalar:
                    pass
                elif _on == Aep.PropertyControlType.slider:
                    pass



        def _write__seq(self, io=None):
            super(Aep.PardBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u1(int(self.property_control_type))
            self._io.write_bytes((self.name).encode(u"windows-1252"))
            self._io.write_bytes(self._unnamed3)
            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.last_color)):
                    pass
                    self._io.write_u1(self.last_color[i])


            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.default_color)):
                    pass
                    self._io.write_u1(self.default_color[i])


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.angle) or (self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.angle:
                    pass
                    self._io.write_s4be(self.last_value)
                elif _on == Aep.PropertyControlType.boolean:
                    pass
                    self._io.write_u4be(self.last_value)
                elif _on == Aep.PropertyControlType.enum:
                    pass
                    self._io.write_u4be(self.last_value)
                elif _on == Aep.PropertyControlType.scalar:
                    pass
                    self._io.write_s4be(self.last_value)
                elif _on == Aep.PropertyControlType.slider:
                    pass
                    self._io.write_f8be(self.last_value)

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                    self._io.write_f8be(self.last_value_x_raw)
                elif _on == Aep.PropertyControlType.two_d:
                    pass
                    self._io.write_s4be(self.last_value_x_raw)

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                    self._io.write_f8be(self.last_value_y_raw)
                elif _on == Aep.PropertyControlType.two_d:
                    pass
                    self._io.write_s4be(self.last_value_y_raw)

            if self.property_control_type == Aep.PropertyControlType.three_d:
                pass
                self._io.write_f8be(self.last_value_z_raw)

            if self.property_control_type == Aep.PropertyControlType.enum:
                pass
                self._io.write_s4be(self.nb_options)

            if  ((self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.boolean:
                    pass
                    self._io.write_u1(self.default)
                elif _on == Aep.PropertyControlType.enum:
                    pass
                    self._io.write_s4be(self.default)

            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.color) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                self._io.write_bytes(self._unnamed12)

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass
                self._io.write_s2be(self.min_value)

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass
                self._io.write_bytes(self._unnamed14)

            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                for i in range(len(self.max_color)):
                    pass
                    self._io.write_u1(self.max_color[i])


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.scalar:
                    pass
                    self._io.write_s2be(self.max_value)
                elif _on == Aep.PropertyControlType.slider:
                    pass
                    self._io.write_f4be(self.max_value)

            self._io.write_bytes(self._unnamed17)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed17", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 15:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 15, len(self._unnamed0))
            if len((self.name).encode(u"windows-1252")) != 32:
                raise kaitaistruct.ConsistencyError(u"name", 32, len((self.name).encode(u"windows-1252")))
            if len(self._unnamed3) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed3", 8, len(self._unnamed3))
            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                if len(self.last_color) != 4:
                    raise kaitaistruct.ConsistencyError(u"last_color", 4, len(self.last_color))
                for i in range(len(self.last_color)):
                    pass


            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                if len(self.default_color) != 4:
                    raise kaitaistruct.ConsistencyError(u"default_color", 4, len(self.default_color))
                for i in range(len(self.default_color)):
                    pass


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.angle) or (self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.angle:
                    pass
                elif _on == Aep.PropertyControlType.boolean:
                    pass
                elif _on == Aep.PropertyControlType.enum:
                    pass
                elif _on == Aep.PropertyControlType.scalar:
                    pass
                elif _on == Aep.PropertyControlType.slider:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                elif _on == Aep.PropertyControlType.two_d:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.three_d:
                    pass
                elif _on == Aep.PropertyControlType.two_d:
                    pass

            if self.property_control_type == Aep.PropertyControlType.three_d:
                pass

            if self.property_control_type == Aep.PropertyControlType.enum:
                pass

            if  ((self.property_control_type == Aep.PropertyControlType.boolean) or (self.property_control_type == Aep.PropertyControlType.enum)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.boolean:
                    pass
                elif _on == Aep.PropertyControlType.enum:
                    pass

            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.color) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                if len(self._unnamed12) != (72 if self.property_control_type == Aep.PropertyControlType.scalar else (64 if self.property_control_type == Aep.PropertyControlType.color else 52)):
                    raise kaitaistruct.ConsistencyError(u"_unnamed12", (72 if self.property_control_type == Aep.PropertyControlType.scalar else (64 if self.property_control_type == Aep.PropertyControlType.color else 52)), len(self._unnamed12))

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass

            if self.property_control_type == Aep.PropertyControlType.scalar:
                pass
                if len(self._unnamed14) != 2:
                    raise kaitaistruct.ConsistencyError(u"_unnamed14", 2, len(self._unnamed14))

            if self.property_control_type == Aep.PropertyControlType.color:
                pass
                if len(self.max_color) != 4:
                    raise kaitaistruct.ConsistencyError(u"max_color", 4, len(self.max_color))
                for i in range(len(self.max_color)):
                    pass


            if  ((self.property_control_type == Aep.PropertyControlType.scalar) or (self.property_control_type == Aep.PropertyControlType.slider)) :
                pass
                _on = self.property_control_type
                if _on == Aep.PropertyControlType.scalar:
                    pass
                elif _on == Aep.PropertyControlType.slider:
                    pass

            self._dirty = False

        @property
        def last_value_x(self):
            if hasattr(self, '_m_last_value_x'):
                return self._m_last_value_x

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                self._m_last_value_x = self.last_value_x_raw * (1.0 / 128 if self.property_control_type == Aep.PropertyControlType.two_d else 512)

            return getattr(self, '_m_last_value_x', None)

        def _invalidate_last_value_x(self):
            del self._m_last_value_x
        @property
        def last_value_y(self):
            if hasattr(self, '_m_last_value_y'):
                return self._m_last_value_y

            if  ((self.property_control_type == Aep.PropertyControlType.two_d) or (self.property_control_type == Aep.PropertyControlType.three_d)) :
                pass
                self._m_last_value_y = self.last_value_y_raw * (1.0 / 128 if self.property_control_type == Aep.PropertyControlType.two_d else 512)

            return getattr(self, '_m_last_value_y', None)

        def _invalidate_last_value_y(self):
            del self._m_last_value_y
        @property
        def last_value_z(self):
            if hasattr(self, '_m_last_value_z'):
                return self._m_last_value_z

            if self.property_control_type == Aep.PropertyControlType.three_d:
                pass
                self._m_last_value_z = self.last_value_z_raw * 512

            return getattr(self, '_m_last_value_z', None)

        def _invalidate_last_value_z(self):
            del self._m_last_value_z

    class ParnBody(ReadWriteKaitaiStruct):
        """Parameter count inside a LIST parT. Contains the number of tdmn/pard
        parameter entries that follow.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.ParnBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.count = self._io.read_u4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.ParnBody, self)._write__seq(io)
            self._io.write_u4be(self.count)


        def _check(self):
            self._dirty = False


    class PngRoptData(ReadWriteKaitaiStruct):
        """PNG format-specific render options.
        Contains width, height, and bit depth at known offsets.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.PngRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(14)
            self.width = self._io.read_u4be()
            self.height = self._io.read_u4be()
            self._unnamed3 = self._io.read_bytes(2)
            self.bit_depth = self._io.read_u2be()
            self.compression = self._io.read_u4be()
            self._unnamed6 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.PngRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u4be(self.width)
            self._io.write_u4be(self.height)
            self._io.write_bytes(self._unnamed3)
            self._io.write_u2be(self.bit_depth)
            self._io.write_u4be(self.compression)
            self._io.write_bytes(self._unnamed6)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 14:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 14, len(self._unnamed0))
            if len(self._unnamed3) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed3", 2, len(self._unnamed3))
            self._dirty = False


    class PrgbBody(ReadWriteKaitaiStruct):
        """Preserve RGB flag for footage color management.
        Inside LIST:CLRS in a footage item's LIST:Pin.
        When this chunk is present, Preserve RGB is enabled.
        Prevents color shifts during alpha compositing in linear color.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.PrgbBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(1)
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, self._io, u"/types/prgb_body/seq/0")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.PrgbBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)


        def _check(self):
            if len(self._unnamed0) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 1, len(self._unnamed0))
            if not self._unnamed0 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed0, None, u"/types/prgb_body/seq/0")
            self._dirty = False


    class PrinBody(ReadWriteKaitaiStruct):
        """Composition renderer info.
        Contains the internal match name and the display name of the
        active 3D renderer plug-in (e.g. "Classic 3D", "Cinema 4D").
        Found inside LIST:PRin of a composition's LIST:Item.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.PrinBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(4)
            self.match_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(48), 0, False)).decode(u"ASCII")
            self.display_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(48), 0, False)).decode(u"ASCII")
            self._unnamed3 = self._io.read_bytes(3)
            self._unnamed4 = self._io.read_bytes(1)
            if not self._unnamed4 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed4, self._io, u"/types/prin_body/seq/4")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.PrinBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bytes_limit((self.match_name).encode(u"ASCII"), 48, 0, 0)
            self._io.write_bytes_limit((self.display_name).encode(u"ASCII"), 48, 0, 0)
            self._io.write_bytes(self._unnamed3)
            self._io.write_bytes(self._unnamed4)


        def _check(self):
            if len(self._unnamed0) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 4, len(self._unnamed0))
            if len((self.match_name).encode(u"ASCII")) > 48:
                raise kaitaistruct.ConsistencyError(u"match_name", 48, len((self.match_name).encode(u"ASCII")))
            if KaitaiStream.byte_array_index_of((self.match_name).encode(u"ASCII"), 0) != -1:
                raise kaitaistruct.ConsistencyError(u"match_name", -1, KaitaiStream.byte_array_index_of((self.match_name).encode(u"ASCII"), 0))
            if len((self.display_name).encode(u"ASCII")) > 48:
                raise kaitaistruct.ConsistencyError(u"display_name", 48, len((self.display_name).encode(u"ASCII")))
            if KaitaiStream.byte_array_index_of((self.display_name).encode(u"ASCII"), 0) != -1:
                raise kaitaistruct.ConsistencyError(u"display_name", -1, KaitaiStream.byte_array_index_of((self.display_name).encode(u"ASCII"), 0))
            if len(self._unnamed3) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed3", 3, len(self._unnamed3))
            if len(self._unnamed4) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 1, len(self._unnamed4))
            if not self._unnamed4 == b"\x01":
                raise kaitaistruct.ValidationNotEqualError(b"\x01", self._unnamed4, None, u"/types/prin_body/seq/4")
            self._dirty = False


    class RenderSettingsLdatBody(ReadWriteKaitaiStruct):
        """Render settings ldat chunk (2246 bytes)."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RenderSettingsLdatBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(7)
            self._unnamed1 = self._io.read_bits_int_be(5)
            self.queue_item_notify = self._io.read_bits_int_be(1) != 0
            self._unnamed3 = self._io.read_bits_int_be(2)
            self.comp_id = self._io.read_u4be()
            self.status = self._io.read_u4be()
            self._unnamed6 = self._io.read_bytes(4)
            self.time_span_start_dividend = self._io.read_u4be()
            self.time_span_start_divisor = self._io.read_u4be()
            self.time_span_duration_dividend = self._io.read_u4be()
            self.time_span_duration_divisor = self._io.read_u4be()
            self._unnamed11 = self._io.read_bytes(8)
            self.frame_rate_integer = self._io.read_u2be()
            self.frame_rate_fractional = self._io.read_u2be()
            self._unnamed14 = self._io.read_bytes(2)
            self.field_render = self._io.read_u2be()
            self._unnamed16 = self._io.read_bytes(2)
            self.pulldown = self._io.read_u2be()
            self.quality = self._io.read_u2be()
            self.resolution_x = self._io.read_u2be()
            self.resolution_y = self._io.read_u2be()
            self._unnamed21 = self._io.read_bytes(2)
            self.effects = self._io.read_u2be()
            self._unnamed23 = self._io.read_bytes(2)
            self.proxy_use = self._io.read_u2be()
            self._unnamed25 = self._io.read_bytes(2)
            self.motion_blur = self._io.read_u2be()
            self._unnamed27 = self._io.read_bytes(2)
            self.frame_blending = self._io.read_u2be()
            self._unnamed29 = self._io.read_bytes(2)
            self.log_type = self._io.read_u2be()
            self._unnamed31 = self._io.read_bytes(2)
            self.skip_existing_files = self._io.read_u2be()
            self._unnamed33 = self._io.read_bytes(4)
            self.template_name = (KaitaiStream.bytes_terminate(self._io.read_bytes(64), 0, False)).decode(u"ASCII")
            self._unnamed35 = self._io.read_bytes(1990)
            self.use_this_frame_rate = self._io.read_u2be()
            self._unnamed37 = self._io.read_bytes(2)
            self.time_span_source = self._io.read_u2be()
            self._unnamed39 = self._io.read_bytes(14)
            self.solo_switches = self._io.read_u2be()
            self._unnamed41 = self._io.read_bytes(2)
            self.disk_cache = self._io.read_u2be()
            self._unnamed43 = self._io.read_bytes(2)
            self.guide_layers = self._io.read_u2be()
            self._unnamed45 = self._io.read_bytes(6)
            self.color_depth = self._io.read_u2be()
            self._unnamed47 = self._io.read_bytes(16)
            self.start_time = self._io.read_u4be()
            self.elapsed_seconds = self._io.read_u4be()
            self._unnamed50 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.RenderSettingsLdatBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(5, self._unnamed1)
            self._io.write_bits_int_be(1, int(self.queue_item_notify))
            self._io.write_bits_int_be(2, self._unnamed3)
            self._io.write_u4be(self.comp_id)
            self._io.write_u4be(self.status)
            self._io.write_bytes(self._unnamed6)
            self._io.write_u4be(self.time_span_start_dividend)
            self._io.write_u4be(self.time_span_start_divisor)
            self._io.write_u4be(self.time_span_duration_dividend)
            self._io.write_u4be(self.time_span_duration_divisor)
            self._io.write_bytes(self._unnamed11)
            self._io.write_u2be(self.frame_rate_integer)
            self._io.write_u2be(self.frame_rate_fractional)
            self._io.write_bytes(self._unnamed14)
            self._io.write_u2be(self.field_render)
            self._io.write_bytes(self._unnamed16)
            self._io.write_u2be(self.pulldown)
            self._io.write_u2be(self.quality)
            self._io.write_u2be(self.resolution_x)
            self._io.write_u2be(self.resolution_y)
            self._io.write_bytes(self._unnamed21)
            self._io.write_u2be(self.effects)
            self._io.write_bytes(self._unnamed23)
            self._io.write_u2be(self.proxy_use)
            self._io.write_bytes(self._unnamed25)
            self._io.write_u2be(self.motion_blur)
            self._io.write_bytes(self._unnamed27)
            self._io.write_u2be(self.frame_blending)
            self._io.write_bytes(self._unnamed29)
            self._io.write_u2be(self.log_type)
            self._io.write_bytes(self._unnamed31)
            self._io.write_u2be(self.skip_existing_files)
            self._io.write_bytes(self._unnamed33)
            self._io.write_bytes_limit((self.template_name).encode(u"ASCII"), 64, 0, 0)
            self._io.write_bytes(self._unnamed35)
            self._io.write_u2be(self.use_this_frame_rate)
            self._io.write_bytes(self._unnamed37)
            self._io.write_u2be(self.time_span_source)
            self._io.write_bytes(self._unnamed39)
            self._io.write_u2be(self.solo_switches)
            self._io.write_bytes(self._unnamed41)
            self._io.write_u2be(self.disk_cache)
            self._io.write_bytes(self._unnamed43)
            self._io.write_u2be(self.guide_layers)
            self._io.write_bytes(self._unnamed45)
            self._io.write_u2be(self.color_depth)
            self._io.write_bytes(self._unnamed47)
            self._io.write_u4be(self.start_time)
            self._io.write_u4be(self.elapsed_seconds)
            self._io.write_bytes(self._unnamed50)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed50", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 7, len(self._unnamed0))
            if len(self._unnamed6) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 4, len(self._unnamed6))
            if len(self._unnamed11) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 8, len(self._unnamed11))
            if len(self._unnamed14) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed14", 2, len(self._unnamed14))
            if len(self._unnamed16) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed16", 2, len(self._unnamed16))
            if len(self._unnamed21) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed21", 2, len(self._unnamed21))
            if len(self._unnamed23) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed23", 2, len(self._unnamed23))
            if len(self._unnamed25) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed25", 2, len(self._unnamed25))
            if len(self._unnamed27) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed27", 2, len(self._unnamed27))
            if len(self._unnamed29) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed29", 2, len(self._unnamed29))
            if len(self._unnamed31) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed31", 2, len(self._unnamed31))
            if len(self._unnamed33) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed33", 4, len(self._unnamed33))
            if len((self.template_name).encode(u"ASCII")) > 64:
                raise kaitaistruct.ConsistencyError(u"template_name", 64, len((self.template_name).encode(u"ASCII")))
            if KaitaiStream.byte_array_index_of((self.template_name).encode(u"ASCII"), 0) != -1:
                raise kaitaistruct.ConsistencyError(u"template_name", -1, KaitaiStream.byte_array_index_of((self.template_name).encode(u"ASCII"), 0))
            if len(self._unnamed35) != 1990:
                raise kaitaistruct.ConsistencyError(u"_unnamed35", 1990, len(self._unnamed35))
            if len(self._unnamed37) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed37", 2, len(self._unnamed37))
            if len(self._unnamed39) != 14:
                raise kaitaistruct.ConsistencyError(u"_unnamed39", 14, len(self._unnamed39))
            if len(self._unnamed41) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed41", 2, len(self._unnamed41))
            if len(self._unnamed43) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed43", 2, len(self._unnamed43))
            if len(self._unnamed45) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed45", 6, len(self._unnamed45))
            if len(self._unnamed47) != 16:
                raise kaitaistruct.ConsistencyError(u"_unnamed47", 16, len(self._unnamed47))
            self._dirty = False

        @property
        def frame_rate(self):
            """Frame rate in fps (integer + fractional)."""
            if hasattr(self, '_m_frame_rate'):
                return self._m_frame_rate

            self._m_frame_rate = self.frame_rate_integer + (self.frame_rate_fractional * 1.0) / 65536
            return getattr(self, '_m_frame_rate', None)

        def _invalidate_frame_rate(self):
            del self._m_frame_rate
        @property
        def time_span_duration(self):
            """Time span duration in seconds."""
            if hasattr(self, '_m_time_span_duration'):
                return self._m_time_span_duration

            self._m_time_span_duration = ((self.time_span_duration_dividend * 1.0) / self.time_span_duration_divisor if self.time_span_duration_divisor != 0 else 0)
            return getattr(self, '_m_time_span_duration', None)

        def _invalidate_time_span_duration(self):
            del self._m_time_span_duration
        @property
        def time_span_start(self):
            """Time span start in seconds."""
            if hasattr(self, '_m_time_span_start'):
                return self._m_time_span_start

            self._m_time_span_start = ((self.time_span_start_dividend * 1.0) / self.time_span_start_divisor if self.time_span_start_divisor != 0 else 0)
            return getattr(self, '_m_time_span_start', None)

        def _invalidate_time_span_start(self):
            del self._m_time_span_start

    class RoouBody(ReadWriteKaitaiStruct):
        """Output module settings (154 bytes)."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RoouBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.magic = self._io.read_bytes(4)
            self.video_codec = (self._io.read_bytes(4)).decode(u"ASCII")
            self._unnamed2 = self._io.read_bytes(8)
            self.starting_number = self._io.read_u4be()
            self._unnamed4 = self._io.read_bytes(6)
            self.format_id = (self._io.read_bytes(4)).decode(u"ASCII")
            self._unnamed6 = self._io.read_bytes(2)
            self._unnamed7 = self._io.read_bytes(4)
            self.width = self._io.read_u2be()
            self._unnamed9 = self._io.read_bytes(2)
            self.height = self._io.read_u2be()
            self._unnamed11 = self._io.read_bytes(25)
            self.frame_rate = self._io.read_u1()
            self._unnamed13 = self._io.read_bytes(3)
            self.depth = self._io.read_u1()
            self._unnamed15 = self._io.read_bytes(5)
            self.color_premultiplied = self._io.read_u1()
            self._unnamed17 = self._io.read_bytes(3)
            self.color_matted = self._io.read_u1()
            self._unnamed19 = self._io.read_bytes(18)
            self.audio_sample_rate = self._io.read_f8be()
            self.audio_disabled_hi = self._io.read_u1()
            self.audio_format = self._io.read_u1()
            self._unnamed23 = self._io.read_bytes(1)
            self.audio_bit_depth = self._io.read_u1()
            self._unnamed25 = self._io.read_bytes(1)
            self.audio_channels = self._io.read_u1()
            self._unnamed27 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.RoouBody, self)._write__seq(io)
            self._io.write_bytes(self.magic)
            self._io.write_bytes((self.video_codec).encode(u"ASCII"))
            self._io.write_bytes(self._unnamed2)
            self._io.write_u4be(self.starting_number)
            self._io.write_bytes(self._unnamed4)
            self._io.write_bytes((self.format_id).encode(u"ASCII"))
            self._io.write_bytes(self._unnamed6)
            self._io.write_bytes(self._unnamed7)
            self._io.write_u2be(self.width)
            self._io.write_bytes(self._unnamed9)
            self._io.write_u2be(self.height)
            self._io.write_bytes(self._unnamed11)
            self._io.write_u1(self.frame_rate)
            self._io.write_bytes(self._unnamed13)
            self._io.write_u1(self.depth)
            self._io.write_bytes(self._unnamed15)
            self._io.write_u1(self.color_premultiplied)
            self._io.write_bytes(self._unnamed17)
            self._io.write_u1(self.color_matted)
            self._io.write_bytes(self._unnamed19)
            self._io.write_f8be(self.audio_sample_rate)
            self._io.write_u1(self.audio_disabled_hi)
            self._io.write_u1(self.audio_format)
            self._io.write_bytes(self._unnamed23)
            self._io.write_u1(self.audio_bit_depth)
            self._io.write_bytes(self._unnamed25)
            self._io.write_u1(self.audio_channels)
            self._io.write_bytes(self._unnamed27)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed27", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self.magic) != 4:
                raise kaitaistruct.ConsistencyError(u"magic", 4, len(self.magic))
            if len((self.video_codec).encode(u"ASCII")) != 4:
                raise kaitaistruct.ConsistencyError(u"video_codec", 4, len((self.video_codec).encode(u"ASCII")))
            if len(self._unnamed2) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 8, len(self._unnamed2))
            if len(self._unnamed4) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 6, len(self._unnamed4))
            if len((self.format_id).encode(u"ASCII")) != 4:
                raise kaitaistruct.ConsistencyError(u"format_id", 4, len((self.format_id).encode(u"ASCII")))
            if len(self._unnamed6) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed6", 2, len(self._unnamed6))
            if len(self._unnamed7) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 4, len(self._unnamed7))
            if len(self._unnamed9) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed9", 2, len(self._unnamed9))
            if len(self._unnamed11) != 25:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 25, len(self._unnamed11))
            if len(self._unnamed13) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed13", 3, len(self._unnamed13))
            if len(self._unnamed15) != 5:
                raise kaitaistruct.ConsistencyError(u"_unnamed15", 5, len(self._unnamed15))
            if len(self._unnamed17) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed17", 3, len(self._unnamed17))
            if len(self._unnamed19) != 18:
                raise kaitaistruct.ConsistencyError(u"_unnamed19", 18, len(self._unnamed19))
            if len(self._unnamed23) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed23", 1, len(self._unnamed23))
            if len(self._unnamed25) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed25", 1, len(self._unnamed25))
            self._dirty = False


    class RoptBody(ReadWriteKaitaiStruct):
        """Format-specific render options for the output module.
        The first 4 bytes identify the format, followed by format-specific data.
        These settings complement the main output module settings in roou_body.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RoptBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.format_code = (self._io.read_bytes(4)).decode(u"ASCII")
            _on = self.format_code
            if _on == u"JPEG":
                pass
                self.body = Aep.JpegRoptData(self._io, self, self._root)
                self.body._read()
            elif _on == u"TIF ":
                pass
                self.body = Aep.TiffRoptData(self._io, self, self._root)
                self.body._read()
            elif _on == u"TPIC":
                pass
                self.body = Aep.TargaRoptData(self._io, self, self._root)
                self.body._read()
            elif _on == u"oEXR":
                pass
                self.body = Aep.OpenexrRoptData(self._io, self, self._root)
                self.body._read()
            elif _on == u"png!":
                pass
                self.body = Aep.PngRoptData(self._io, self, self._root)
                self.body._read()
            elif _on == u"sDPX":
                pass
                self.body = Aep.CineonRoptData(self._io, self, self._root)
                self.body._read()
            else:
                pass
                self.body = Aep.RoptGenericData(self._io, self, self._root)
                self.body._read()
            self._dirty = False


        def _fetch_instances(self):
            pass
            _on = self.format_code
            if _on == u"JPEG":
                pass
                self.body._fetch_instances()
            elif _on == u"TIF ":
                pass
                self.body._fetch_instances()
            elif _on == u"TPIC":
                pass
                self.body._fetch_instances()
            elif _on == u"oEXR":
                pass
                self.body._fetch_instances()
            elif _on == u"png!":
                pass
                self.body._fetch_instances()
            elif _on == u"sDPX":
                pass
                self.body._fetch_instances()
            else:
                pass
                self.body._fetch_instances()


        def _write__seq(self, io=None):
            super(Aep.RoptBody, self)._write__seq(io)
            self._io.write_bytes((self.format_code).encode(u"ASCII"))
            _on = self.format_code
            if _on == u"JPEG":
                pass
                self.body._write__seq(self._io)
            elif _on == u"TIF ":
                pass
                self.body._write__seq(self._io)
            elif _on == u"TPIC":
                pass
                self.body._write__seq(self._io)
            elif _on == u"oEXR":
                pass
                self.body._write__seq(self._io)
            elif _on == u"png!":
                pass
                self.body._write__seq(self._io)
            elif _on == u"sDPX":
                pass
                self.body._write__seq(self._io)
            else:
                pass
                self.body._write__seq(self._io)


        def _check(self):
            if len((self.format_code).encode(u"ASCII")) != 4:
                raise kaitaistruct.ConsistencyError(u"format_code", 4, len((self.format_code).encode(u"ASCII")))
            _on = self.format_code
            if _on == u"JPEG":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"TIF ":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"TPIC":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"oEXR":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"png!":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            elif _on == u"sDPX":
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            else:
                pass
                if self.body._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"body", self._root, self.body._root)
                if self.body._parent != self:
                    raise kaitaistruct.ConsistencyError(u"body", self, self.body._parent)
            self._dirty = False


    class RoptGenericData(ReadWriteKaitaiStruct):
        """Generic render options data for formats without specific parsing."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RoptGenericData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.raw = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.RoptGenericData, self)._write__seq(io)
            self._io.write_bytes(self.raw)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"raw", 0, self._io.size() - self._io.pos())


        def _check(self):
            self._dirty = False


    class RoutBody(ReadWriteKaitaiStruct):
        """Render queue item flags (4-byte header + 4 bytes per item)."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RoutBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(4)
            self.items = []
            i = 0
            while not self._io.is_eof():
                _t_items = Aep.RoutItem(self._io, self, self._root)
                try:
                    _t_items._read()
                finally:
                    self.items.append(_t_items)
                i += 1

            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.items)):
                pass
                self.items[i]._fetch_instances()



        def _write__seq(self, io=None):
            super(Aep.RoutBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            for i in range(len(self.items)):
                pass
                if self._io.is_eof():
                    raise kaitaistruct.ConsistencyError(u"items", 0, self._io.size() - self._io.pos())
                self.items[i]._write__seq(self._io)

            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"items", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 4, len(self._unnamed0))
            for i in range(len(self.items)):
                pass
                if self.items[i]._root != self._root:
                    raise kaitaistruct.ConsistencyError(u"items", self._root, self.items[i]._root)
                if self.items[i]._parent != self:
                    raise kaitaistruct.ConsistencyError(u"items", self, self.items[i]._parent)

            self._dirty = False


    class RoutItem(ReadWriteKaitaiStruct):
        """Per-item render queue flags (4 bytes)."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.RoutItem, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bits_int_be(1) != 0
            self.render = self._io.read_bits_int_be(1) != 0
            self._unnamed2 = self._io.read_bits_int_be(6)
            self._unnamed3 = self._io.read_bytes(3)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.RoutItem, self)._write__seq(io)
            self._io.write_bits_int_be(1, int(self._unnamed0))
            self._io.write_bits_int_be(1, int(self.render))
            self._io.write_bits_int_be(6, self._unnamed2)
            self._io.write_bytes(self._unnamed3)


        def _check(self):
            if len(self._unnamed3) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed3", 3, len(self._unnamed3))
            self._dirty = False


    class S4Body(ReadWriteKaitaiStruct):
        """Single signed 32-bit integer value."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.S4Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.value = self._io.read_s4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.S4Body, self)._write__seq(io)
            self._io.write_s4be(self.value)


        def _check(self):
            self._dirty = False


    class ShapePoint(ReadWriteKaitaiStruct):
        """A single normalized bezier point in a shape path.
        Coordinates are f4 values in the [0, 1] range,
        relative to the bounding box defined in shph_body.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.ShapePoint, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.x = self._io.read_f4be()
            self.y = self._io.read_f4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.ShapePoint, self)._write__seq(io)
            self._io.write_f4be(self.x)
            self._io.write_f4be(self.y)


        def _check(self):
            self._dirty = False


    class ShphBody(ReadWriteKaitaiStruct):
        """Shape path header. Contains a closed/open flag and the bounding box
        for the shape vertices.  Vertex coordinates in the associated ldat
        are normalized to [0, 1] relative to this bounding box.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.ShphBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(3)
            self._unnamed1 = self._io.read_bits_int_be(4)
            self.open = self._io.read_bits_int_be(1) != 0
            self._unnamed3 = self._io.read_bits_int_be(3)
            self.top_left_x = self._io.read_f4be()
            self.top_left_y = self._io.read_f4be()
            self.bottom_right_x = self._io.read_f4be()
            self.bottom_right_y = self._io.read_f4be()
            self._unnamed8 = self._io.read_bytes(4)
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.ShphBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bits_int_be(4, self._unnamed1)
            self._io.write_bits_int_be(1, int(self.open))
            self._io.write_bits_int_be(3, self._unnamed3)
            self._io.write_f4be(self.top_left_x)
            self._io.write_f4be(self.top_left_y)
            self._io.write_f4be(self.bottom_right_x)
            self._io.write_f4be(self.bottom_right_y)
            self._io.write_bytes(self._unnamed8)


        def _check(self):
            if len(self._unnamed0) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 3, len(self._unnamed0))
            if len(self._unnamed8) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed8", 4, len(self._unnamed8))
            self._dirty = False


    class SspcBody(ReadWriteKaitaiStruct):
        """Source footage settings chunk. Contains dimension, timing, and alpha/field settings.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.SspcBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(22)
            self.source_format_type = (self._io.read_bytes(4)).decode(u"ASCII")
            self._unnamed2 = self._io.read_bytes(6)
            self.width = self._io.read_u2be()
            self._unnamed4 = self._io.read_bytes(2)
            self.height = self._io.read_u2be()
            self.duration_dividend = self._io.read_u4be()
            self.duration_divisor = self._io.read_u4be()
            self._unnamed8 = self._io.read_bytes(10)
            self.native_frame_rate_integer = self._io.read_u4be()
            self.native_frame_rate_fractional = self._io.read_u2be()
            self._unnamed11 = self._io.read_bytes(7)
            self._unnamed12 = self._io.read_bits_int_be(6)
            self.invert_alpha = self._io.read_bits_int_be(1) != 0
            self.premultiplied = self._io.read_bits_int_be(1) != 0
            self.premul_color = []
            for i in range(3):
                self.premul_color.append(self._io.read_u1())

            self.alpha_mode_raw = self._io.read_u1()
            self._unnamed17 = self._io.read_bytes(9)
            self.field_separation_type_raw = self._io.read_u1()
            self._unnamed19 = self._io.read_bytes(3)
            self.field_order = self._io.read_u1()
            self._unnamed21 = self._io.read_bytes(27)
            self.footage_missing_at_save = self._io.read_u1()
            self._unnamed23 = self._io.read_bytes(13)
            self.loop = self._io.read_u1()
            self._unnamed25 = self._io.read_bytes(6)
            self.pixel_ratio_dividend = self._io.read_u4be()
            self.pixel_ratio_divisor = self._io.read_u4be()
            self._unnamed28 = self._io.read_bytes(3)
            self.remove_pulldown = self._io.read_u1()
            self.conform_frame_rate_integer = self._io.read_u2be()
            self.conform_frame_rate_fractional = self._io.read_u2be()
            self._unnamed32 = self._io.read_bytes(7)
            self.high_quality_field_separation = self._io.read_u1()
            self.audio_sample_rate = self._io.read_f8be()
            self._unnamed35 = self._io.read_bytes(4)
            self.start_frame = self._io.read_u4be()
            self.end_frame = self._io.read_u4be()
            self.frame_padding = self._io.read_u4be()
            self._unnamed39 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.premul_color)):
                pass



        def _write__seq(self, io=None):
            super(Aep.SspcBody, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_bytes((self.source_format_type).encode(u"ASCII"))
            self._io.write_bytes(self._unnamed2)
            self._io.write_u2be(self.width)
            self._io.write_bytes(self._unnamed4)
            self._io.write_u2be(self.height)
            self._io.write_u4be(self.duration_dividend)
            self._io.write_u4be(self.duration_divisor)
            self._io.write_bytes(self._unnamed8)
            self._io.write_u4be(self.native_frame_rate_integer)
            self._io.write_u2be(self.native_frame_rate_fractional)
            self._io.write_bytes(self._unnamed11)
            self._io.write_bits_int_be(6, self._unnamed12)
            self._io.write_bits_int_be(1, int(self.invert_alpha))
            self._io.write_bits_int_be(1, int(self.premultiplied))
            for i in range(len(self.premul_color)):
                pass
                self._io.write_u1(self.premul_color[i])

            self._io.write_u1(self.alpha_mode_raw)
            self._io.write_bytes(self._unnamed17)
            self._io.write_u1(self.field_separation_type_raw)
            self._io.write_bytes(self._unnamed19)
            self._io.write_u1(self.field_order)
            self._io.write_bytes(self._unnamed21)
            self._io.write_u1(self.footage_missing_at_save)
            self._io.write_bytes(self._unnamed23)
            self._io.write_u1(self.loop)
            self._io.write_bytes(self._unnamed25)
            self._io.write_u4be(self.pixel_ratio_dividend)
            self._io.write_u4be(self.pixel_ratio_divisor)
            self._io.write_bytes(self._unnamed28)
            self._io.write_u1(self.remove_pulldown)
            self._io.write_u2be(self.conform_frame_rate_integer)
            self._io.write_u2be(self.conform_frame_rate_fractional)
            self._io.write_bytes(self._unnamed32)
            self._io.write_u1(self.high_quality_field_separation)
            self._io.write_f8be(self.audio_sample_rate)
            self._io.write_bytes(self._unnamed35)
            self._io.write_u4be(self.start_frame)
            self._io.write_u4be(self.end_frame)
            self._io.write_u4be(self.frame_padding)
            self._io.write_bytes(self._unnamed39)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed39", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 22:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 22, len(self._unnamed0))
            if len((self.source_format_type).encode(u"ASCII")) != 4:
                raise kaitaistruct.ConsistencyError(u"source_format_type", 4, len((self.source_format_type).encode(u"ASCII")))
            if len(self._unnamed2) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 6, len(self._unnamed2))
            if len(self._unnamed4) != 2:
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 2, len(self._unnamed4))
            if len(self._unnamed8) != 10:
                raise kaitaistruct.ConsistencyError(u"_unnamed8", 10, len(self._unnamed8))
            if len(self._unnamed11) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 7, len(self._unnamed11))
            if len(self.premul_color) != 3:
                raise kaitaistruct.ConsistencyError(u"premul_color", 3, len(self.premul_color))
            for i in range(len(self.premul_color)):
                pass

            if len(self._unnamed17) != 9:
                raise kaitaistruct.ConsistencyError(u"_unnamed17", 9, len(self._unnamed17))
            if len(self._unnamed19) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed19", 3, len(self._unnamed19))
            if len(self._unnamed21) != 27:
                raise kaitaistruct.ConsistencyError(u"_unnamed21", 27, len(self._unnamed21))
            if len(self._unnamed23) != 13:
                raise kaitaistruct.ConsistencyError(u"_unnamed23", 13, len(self._unnamed23))
            if len(self._unnamed25) != 6:
                raise kaitaistruct.ConsistencyError(u"_unnamed25", 6, len(self._unnamed25))
            if len(self._unnamed28) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed28", 3, len(self._unnamed28))
            if len(self._unnamed32) != 7:
                raise kaitaistruct.ConsistencyError(u"_unnamed32", 7, len(self._unnamed32))
            if len(self._unnamed35) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed35", 4, len(self._unnamed35))
            self._dirty = False

        @property
        def conform_frame_rate(self):
            """A frame rate to use instead of native_frame_rate.
            0 means no conforming (use native_frame_rate).
            """
            if hasattr(self, '_m_conform_frame_rate'):
                return self._m_conform_frame_rate

            self._m_conform_frame_rate = self.conform_frame_rate_integer + self.conform_frame_rate_fractional / 65536.0
            return getattr(self, '_m_conform_frame_rate', None)

        def _invalidate_conform_frame_rate(self):
            del self._m_conform_frame_rate
        @property
        def display_frame_rate(self):
            """The effective frame rate as displayed and rendered.
            If removePulldown is active, multiplied by 0.8.
            """
            if hasattr(self, '_m_display_frame_rate'):
                return self._m_display_frame_rate

            self._m_display_frame_rate = (self.conform_frame_rate if self.conform_frame_rate != 0 else self.native_frame_rate) * (0.8 if self.remove_pulldown != 0 else 1.0)
            return getattr(self, '_m_display_frame_rate', None)

        def _invalidate_display_frame_rate(self):
            del self._m_display_frame_rate
        @property
        def duration(self):
            """Total duration of the footage item in seconds.
            Accounts for conform frame rate and loop count.
            Pulldown does not affect duration (frame rate reduction and
            frame removal cancel out).
            """
            if hasattr(self, '_m_duration'):
                return self._m_duration

            self._m_duration = (self.source_duration * (self.native_frame_rate / self.conform_frame_rate if self.conform_frame_rate != 0 else 1)) * self.loop
            return getattr(self, '_m_duration', None)

        def _invalidate_duration(self):
            del self._m_duration
        @property
        def field_separation_type(self):
            """Combined field separation mode.
            0 = OFF, 1 = UPPER_FIELD_FIRST, 2 = LOWER_FIELD_FIRST
            """
            if hasattr(self, '_m_field_separation_type'):
                return self._m_field_separation_type

            self._m_field_separation_type = (0 if self.field_separation_type_raw == 0 else self.field_order + 1)
            return getattr(self, '_m_field_separation_type', None)

        def _invalidate_field_separation_type(self):
            del self._m_field_separation_type
        @property
        def frame_duration(self):
            """Total number of frames in the footage item."""
            if hasattr(self, '_m_frame_duration'):
                return self._m_frame_duration

            self._m_frame_duration = self.duration * self.display_frame_rate
            return getattr(self, '_m_frame_duration', None)

        def _invalidate_frame_duration(self):
            del self._m_frame_duration
        @property
        def has_alpha(self):
            """True if footage has an alpha channel (3 means no_alpha)."""
            if hasattr(self, '_m_has_alpha'):
                return self._m_has_alpha

            self._m_has_alpha = self.alpha_mode_raw != 3
            return getattr(self, '_m_has_alpha', None)

        def _invalidate_has_alpha(self):
            del self._m_has_alpha
        @property
        def has_audio(self):
            """True if footage has an audio component."""
            if hasattr(self, '_m_has_audio'):
                return self._m_has_audio

            self._m_has_audio = self.audio_sample_rate > 0
            return getattr(self, '_m_has_audio', None)

        def _invalidate_has_audio(self):
            del self._m_has_audio
        @property
        def native_frame_rate(self):
            """The native frame rate of the footage."""
            if hasattr(self, '_m_native_frame_rate'):
                return self._m_native_frame_rate

            self._m_native_frame_rate = self.native_frame_rate_integer + self.native_frame_rate_fractional / 65536.0
            return getattr(self, '_m_native_frame_rate', None)

        def _invalidate_native_frame_rate(self):
            del self._m_native_frame_rate
        @property
        def pixel_aspect(self):
            if hasattr(self, '_m_pixel_aspect'):
                return self._m_pixel_aspect

            self._m_pixel_aspect = (self.pixel_ratio_dividend * 1.0) / self.pixel_ratio_divisor
            return getattr(self, '_m_pixel_aspect', None)

        def _invalidate_pixel_aspect(self):
            del self._m_pixel_aspect
        @property
        def source_duration(self):
            """Raw duration of the source footage in seconds (before conform/loop)."""
            if hasattr(self, '_m_source_duration'):
                return self._m_source_duration

            self._m_source_duration = (self.duration_dividend * 1.0) / self.duration_divisor
            return getattr(self, '_m_source_duration', None)

        def _invalidate_source_duration(self):
            del self._m_source_duration

    class TargaRoptData(ReadWriteKaitaiStruct):
        """Targa (TGA) format-specific render options.
        These correspond to the Targa Options dialog in After Effects.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.TargaRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(73)
            self.bits_per_pixel = self._io.read_u1()
            self._unnamed2 = self._io.read_bytes(4)
            self.rle_compression = self._io.read_u1()
            self._unnamed4 = self._io.read_bytes_full()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.TargaRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u1(self.bits_per_pixel)
            self._io.write_bytes(self._unnamed2)
            self._io.write_u1(self.rle_compression)
            self._io.write_bytes(self._unnamed4)
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"_unnamed4", 0, self._io.size() - self._io.pos())


        def _check(self):
            if len(self._unnamed0) != 73:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 73, len(self._unnamed0))
            if len(self._unnamed2) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 4, len(self._unnamed2))
            self._dirty = False


    class Tdb4Body(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Tdb4Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.magic = self._io.read_bytes(2)
            if not self.magic == b"\xDB\x99":
                raise kaitaistruct.ValidationNotEqualError(b"\xDB\x99", self.magic, self._io, u"/types/tdb4_body/seq/0")
            self.dimensions = self._io.read_u2be()
            self._unnamed2 = self._io.read_bytes(1)
            self._unnamed3 = self._io.read_bits_int_be(4)
            self.is_spatial = self._io.read_bits_int_be(1) != 0
            self._unnamed5 = self._io.read_bits_int_be(2)
            self.static = self._io.read_bits_int_be(1) != 0
            self._unnamed7 = self._io.read_bytes(5)
            self._unnamed8 = self._io.read_bits_int_be(6)
            self.can_vary_over_time = self._io.read_bits_int_be(1) != 0
            self._unnamed10 = self._io.read_bits_int_be(1) != 0
            self._unnamed11 = self._io.read_bytes(4)
            self.unknown_floats = []
            for i in range(5):
                self.unknown_floats.append(self._io.read_f8be())

            self._unnamed13 = self._io.read_bytes(1)
            self._unnamed14 = self._io.read_bits_int_be(7)
            self.no_value = self._io.read_bits_int_be(1) != 0
            self._unnamed16 = self._io.read_bytes(1)
            self._unnamed17 = self._io.read_bits_int_be(4)
            self.vector = self._io.read_bits_int_be(1) != 0
            self.integer = self._io.read_bits_int_be(1) != 0
            self._unnamed20 = self._io.read_bits_int_be(1) != 0
            self.color = self._io.read_bits_int_be(1) != 0
            self._unnamed22 = self._io.read_bytes(8)
            self.animated = self._io.read_u1()
            self._unnamed24 = self._io.read_bytes(15)
            self._unnamed25 = self._io.read_bytes(32)
            self._unnamed26 = self._io.read_bytes(3)
            self._unnamed27 = self._io.read_bits_int_be(7)
            self.expression_disabled = self._io.read_bits_int_be(1) != 0
            self._unnamed29 = self._io.read_bytes(4)
            self._dirty = False


        def _fetch_instances(self):
            pass
            for i in range(len(self.unknown_floats)):
                pass



        def _write__seq(self, io=None):
            super(Aep.Tdb4Body, self)._write__seq(io)
            self._io.write_bytes(self.magic)
            self._io.write_u2be(self.dimensions)
            self._io.write_bytes(self._unnamed2)
            self._io.write_bits_int_be(4, self._unnamed3)
            self._io.write_bits_int_be(1, int(self.is_spatial))
            self._io.write_bits_int_be(2, self._unnamed5)
            self._io.write_bits_int_be(1, int(self.static))
            self._io.write_bytes(self._unnamed7)
            self._io.write_bits_int_be(6, self._unnamed8)
            self._io.write_bits_int_be(1, int(self.can_vary_over_time))
            self._io.write_bits_int_be(1, int(self._unnamed10))
            self._io.write_bytes(self._unnamed11)
            for i in range(len(self.unknown_floats)):
                pass
                self._io.write_f8be(self.unknown_floats[i])

            self._io.write_bytes(self._unnamed13)
            self._io.write_bits_int_be(7, self._unnamed14)
            self._io.write_bits_int_be(1, int(self.no_value))
            self._io.write_bytes(self._unnamed16)
            self._io.write_bits_int_be(4, self._unnamed17)
            self._io.write_bits_int_be(1, int(self.vector))
            self._io.write_bits_int_be(1, int(self.integer))
            self._io.write_bits_int_be(1, int(self._unnamed20))
            self._io.write_bits_int_be(1, int(self.color))
            self._io.write_bytes(self._unnamed22)
            self._io.write_u1(self.animated)
            self._io.write_bytes(self._unnamed24)
            self._io.write_bytes(self._unnamed25)
            self._io.write_bytes(self._unnamed26)
            self._io.write_bits_int_be(7, self._unnamed27)
            self._io.write_bits_int_be(1, int(self.expression_disabled))
            self._io.write_bytes(self._unnamed29)


        def _check(self):
            if len(self.magic) != 2:
                raise kaitaistruct.ConsistencyError(u"magic", 2, len(self.magic))
            if not self.magic == b"\xDB\x99":
                raise kaitaistruct.ValidationNotEqualError(b"\xDB\x99", self.magic, None, u"/types/tdb4_body/seq/0")
            if len(self._unnamed2) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed2", 1, len(self._unnamed2))
            if len(self._unnamed7) != 5:
                raise kaitaistruct.ConsistencyError(u"_unnamed7", 5, len(self._unnamed7))
            if len(self._unnamed11) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed11", 4, len(self._unnamed11))
            if len(self.unknown_floats) != 5:
                raise kaitaistruct.ConsistencyError(u"unknown_floats", 5, len(self.unknown_floats))
            for i in range(len(self.unknown_floats)):
                pass

            if len(self._unnamed13) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed13", 1, len(self._unnamed13))
            if len(self._unnamed16) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed16", 1, len(self._unnamed16))
            if len(self._unnamed22) != 8:
                raise kaitaistruct.ConsistencyError(u"_unnamed22", 8, len(self._unnamed22))
            if len(self._unnamed24) != 15:
                raise kaitaistruct.ConsistencyError(u"_unnamed24", 15, len(self._unnamed24))
            if len(self._unnamed25) != 32:
                raise kaitaistruct.ConsistencyError(u"_unnamed25", 32, len(self._unnamed25))
            if len(self._unnamed26) != 3:
                raise kaitaistruct.ConsistencyError(u"_unnamed26", 3, len(self._unnamed26))
            if len(self._unnamed29) != 4:
                raise kaitaistruct.ConsistencyError(u"_unnamed29", 4, len(self._unnamed29))
            self._dirty = False


    class TdsbBody(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.TdsbBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.roto_bezier = self._io.read_u1()
            self._unnamed1 = self._io.read_bytes(1)
            self._unnamed2 = self._io.read_bits_int_be(3)
            self.locked_ratio = self._io.read_bits_int_be(1) != 0
            self._unnamed4 = self._io.read_bits_int_be(4)
            self._unnamed5 = self._io.read_bits_int_be(6)
            self.dimensions_separated = self._io.read_bits_int_be(1) != 0
            self.enabled = self._io.read_bits_int_be(1) != 0
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.TdsbBody, self)._write__seq(io)
            self._io.write_u1(self.roto_bezier)
            self._io.write_bytes(self._unnamed1)
            self._io.write_bits_int_be(3, self._unnamed2)
            self._io.write_bits_int_be(1, int(self.locked_ratio))
            self._io.write_bits_int_be(4, self._unnamed4)
            self._io.write_bits_int_be(6, self._unnamed5)
            self._io.write_bits_int_be(1, int(self.dimensions_separated))
            self._io.write_bits_int_be(1, int(self.enabled))


        def _check(self):
            if len(self._unnamed1) != 1:
                raise kaitaistruct.ConsistencyError(u"_unnamed1", 1, len(self._unnamed1))
            self._dirty = False


    class TdumBody(ReadWriteKaitaiStruct):
        """Property min/max value inside a tdbs LIST.
        Used for both tdum (min) and tduM (max) chunks.
        Encoding depends on tdb4 sibling flags: color (4x f4),
        integer (u4), or scalar/position/vector (repeated f8).
        """
        def __init__(self, is_color, is_integer, _io=None, _parent=None, _root=None):
            super(Aep.TdumBody, self).__init__(_io)
            self._parent = _parent
            self._root = _root
            self.is_color = is_color
            self.is_integer = is_integer

        def _read(self):
            if  (((not (self.is_color))) and ((not (self.is_integer)))) :
                pass
                self.value_doubles = []
                for i in range(self._parent.len_body // 8):
                    self.value_doubles.append(self._io.read_f8be())


            if self.is_color:
                pass
                self.value_color = []
                for i in range(4):
                    self.value_color.append(self._io.read_f4be())


            if self.is_integer:
                pass
                self.value_integer = self._io.read_u4be()

            self._dirty = False


        def _fetch_instances(self):
            pass
            if  (((not (self.is_color))) and ((not (self.is_integer)))) :
                pass
                for i in range(len(self.value_doubles)):
                    pass


            if self.is_color:
                pass
                for i in range(len(self.value_color)):
                    pass


            if self.is_integer:
                pass



        def _write__seq(self, io=None):
            super(Aep.TdumBody, self)._write__seq(io)
            if  (((not (self.is_color))) and ((not (self.is_integer)))) :
                pass
                for i in range(len(self.value_doubles)):
                    pass
                    self._io.write_f8be(self.value_doubles[i])


            if self.is_color:
                pass
                for i in range(len(self.value_color)):
                    pass
                    self._io.write_f4be(self.value_color[i])


            if self.is_integer:
                pass
                self._io.write_u4be(self.value_integer)



        def _check(self):
            if  (((not (self.is_color))) and ((not (self.is_integer)))) :
                pass
                if len(self.value_doubles) != self._parent.len_body // 8:
                    raise kaitaistruct.ConsistencyError(u"value_doubles", self._parent.len_body // 8, len(self.value_doubles))
                for i in range(len(self.value_doubles)):
                    pass


            if self.is_color:
                pass
                if len(self.value_color) != 4:
                    raise kaitaistruct.ConsistencyError(u"value_color", 4, len(self.value_color))
                for i in range(len(self.value_color)):
                    pass


            if self.is_integer:
                pass

            self._dirty = False


    class TiffRoptData(ReadWriteKaitaiStruct):
        """TIFF format-specific render options.
        These correspond to the TIFF Options dialog in After Effects.
        """
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.TiffRoptData, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self._unnamed0 = self._io.read_bytes(596)
            self.ibm_pc_byte_order = self._io.read_u1()
            self.lzw_compression = self._io.read_u1()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.TiffRoptData, self)._write__seq(io)
            self._io.write_bytes(self._unnamed0)
            self._io.write_u1(self.ibm_pc_byte_order)
            self._io.write_u1(self.lzw_compression)


        def _check(self):
            if len(self._unnamed0) != 596:
                raise kaitaistruct.ConsistencyError(u"_unnamed0", 596, len(self._unnamed0))
            self._dirty = False


    class U4Body(ReadWriteKaitaiStruct):
        """Single unsigned 32-bit integer value."""
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.U4Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.value = self._io.read_u4be()
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.U4Body, self)._write__seq(io)
            self._io.write_u4be(self.value)


        def _check(self):
            self._dirty = False


    class Utf8Body(ReadWriteKaitaiStruct):
        def __init__(self, _io=None, _parent=None, _root=None):
            super(Aep.Utf8Body, self).__init__(_io)
            self._parent = _parent
            self._root = _root

        def _read(self):
            self.contents = (self._io.read_bytes_full()).decode(u"UTF-8")
            self._dirty = False


        def _fetch_instances(self):
            pass


        def _write__seq(self, io=None):
            super(Aep.Utf8Body, self)._write__seq(io)
            self._io.write_bytes((self.contents).encode(u"UTF-8"))
            if not self._io.is_eof():
                raise kaitaistruct.ConsistencyError(u"contents", 0, self._io.size() - self._io.pos())


        def _check(self):
            self._dirty = False



