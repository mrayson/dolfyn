from struct import calcsize, Struct
import bitops as bo
import numpy as np

grav = 9.81
# The starting value for the checksum:
cs0 = int('0xb58c', 0)


def nans(*args, **kwargs):
    out = np.empty(*args, **kwargs)
    if out.dtype.kind == 'f':
        out[:] = np.NaN
    else:
        out[:] = 0
    return out


class BadCheckSum(Exception):
    pass


class DataDef(object):

    def __init__(self, list_of_defs):
        self._names = []
        self._format = []
        self._shape = []
        self._sci_func = []
        self._N = []
        for itm in list_of_defs:
            self._names.append(itm[0])
            self._format.append(itm[1])
            self._shape.append(itm[2])
            self._sci_func.append(itm[3])
            if itm[2] == []:
                self._N.append(1)
            else:
                self._N.append(int(np.prod(itm[2])))
        self._struct = Struct('<' + self.format)
        self.nbyte = calcsize(self.format)
        self._cs_struct = Struct('<' + '{}H'.format(self.nbyte // 2))

    def init_data(self, npings):
        out = {}
        for nm, fmt, shp in zip(self._names, self._format, self._shape):
            # fmt[0] uses only the first format specifier
            # (ie, skip '15x' in 'B15x')
            out[nm] = nans(shp + [npings], dtype=np.dtype(fmt[0]))
        return out

    def read_into(self, fobj, data, ens, cs=None):
        dat_tuple = self.read(fobj, cs=cs)
        for nm, shp, d in zip(self._names, self._shape, dat_tuple):
            try:
                data[nm][..., ens] = d
            except ValueError:
                data[nm][..., ens] = np.asarray(d).reshape(shp)

    @property
    def format(self, ):
        out = ''
        for f, n in zip(self._format, self._N):
            if n >= 1:
                out += '{}'.format(n)
            out += f
        return out

    def read(self, fobj, cs=None):
        bytes = fobj.read(self.nbyte)
        if len(bytes) != self.nbyte:
            raise IOError("End of file.")
        data = self._struct.unpack(bytes)
        if cs is not None:
            if cs is True:
                # if cs is True, then it should be the last value that
                # was read.
                csval = data[-1]
                off = cs0 - csval
            elif isinstance(cs, int):
                csval = cs
                off = cs0
            cs_res = sum(self._cs_struct.unpack(bytes)) + off
            if csval is not False and (cs_res % 65536) != csval:
                raise BadCheckSum('Checksum failed!')
        out = []
        c = 0
        for idx, n in enumerate(self._N):
            if n == 1:
                out.append(data[c])
            else:
                out.append(data[c:(c + n)])
            c += n
        return out

    def read2dict(self, fobj, cs=False):
        return {self._names[idx]: dat
                for idx, dat in enumerate(self.read(fobj, cs=cs))}

    def sci_data(self, data):
        for ky, func in zip(self._names,
                            self._sci_func):
            if func is None:
                continue
            data[ky] = func(data[ky])


class LinFunc(object):
    """A simple linear offset and scaling object.

    Usage:
       scale_func = LinFunc(scale=3, offset=5)

       new_data = scale_func(old_data)

    This will do:
       new_data = (old_data + 5) * 3
    """

    def __init__(self, scale=1, offset=0):
        self.scale = scale
        self.offset = offset

    def __call__(self, array):
        return (array + self.offset) * self.scale


_header = DataDef([
    ('sync', 'B', [], None),
    ('hsz', 'B', [], None),
    ('id', 'B', [], None),
    ('fam', 'B', [], None),
    ('sz', 'H', [], None),
    ('cs', 'H', [], None),
    ('hcs', 'H', [], None),
])

_burst_hdr = DataDef([
    ('ver', 'B', [], None),
    ('DatOffset', 'B', [], None),
    ('config', 'H', [], None),
    ('SerialNum', 'I', [], None),
    ('year', 'B', [], None),
    ('month', 'B', [], None),
    ('day', 'B', [], None),
    ('hour', 'B', [], None),
    ('minute', 'B', [], None),
    ('second', 'B', [], None),
    ('usec100', 'H', [], None),
    ('c_sound', 'H', [], LinFunc(0.1)),  # m/s
    ('temp', 'H', [], LinFunc(0.01)),  # Celsius
    ('press', 'I', [], LinFunc(0.001)),  # dBar
    ('heading', 'H', [], LinFunc(0.01)),  # degrees
    ('pitch', 'H', [], LinFunc(0.01)),  # degrees
    ('roll', 'H', [], LinFunc(0.01)),  # degrees
    ('beam_config', 'H', [], None),
    ('cell_size', 'H', [], LinFunc(0.001)),  # m
    ('blanking', 'H', [], LinFunc(0.01)),  # m
    ('nom_corr', 'B', [], None),  # percent
    ('temp_press', 'B', [], LinFunc(0.2, -20)),  # Celsius
    ('batt_V', 'H', [], LinFunc(0.1)),  # Volts
    ('Mag', 'h', [3], None),
    ('Acc', 'h', [3], LinFunc(1. / 16384)),
    ('ambig_vel', 'h', [], None),
    ('data_desc', 'H', [], None),
    ('xmit_energy', 'H', [], None),
    ('vel_scale', 'b', [], None),
    ('power_level', 'b', [], None),
    ('temp_mag', 'h', [], None),
    ('temp_clock', 'h', [], LinFunc(0.01)),
    ('error', 'H', [], None),
    ('status0', 'H', [], None),
    ('status', 'I', [], None),
    ('ensemble', 'I', [], None)
])

_burst_group_org = {
    # Everything else will be in 'main'
    'signal': ['amp', 'corr'],
    'alt': ['alt_dist', 'alt_quality', 'alt_status',
            'ast_dist', 'ast_quality',
            'ast_offset_time', 'ast_pressure',
            'altraw_nsamp', 'altraw_dist', 'altraw_samp'],
    'echo': ['echo'],
    'orient': ['orientmat',
               'heading', 'pitch', 'roll',
               'ahrs_gyro', 'Mag', 'Acc'],
    'env': ['c_sound', 'temp', 'press'],
    '#sys': ['temp_press', 'temp_mag', 'temp_clock',
             'batt_V', 'ambig_vel', 'xmit_energy',
             'error', 'status0', 'status', 'ensemble',
             'std_pitch', 'std_roll', 'std_heading',
             'std_press'],
}


def calc_burst_struct(config, nb, nc):
    cb = bo.i16ba(config)[::-1]
    flags = {}
    for idx, nm in enumerate([
            'press', 'temp', 'compass', 'tilt',
            None, 'vel', 'amp', 'corr',
            'alt', 'alt_raw', 'ast', 'echo',
            'ahrs', 'p_gd', 'std', None]):
        flags[nm] = cb[idx]
    dd = []
    if flags['vel']:
        dd.append(('vel', 'h', [nb, nc], None))
    if flags['amp']:
        dd.append(('amp', 'B', [nb, nc],
                   LinFunc(0.5)))  # dB
    if flags['corr']:
        dd.append(('corr', 'B', [nb, nc], None))  # percent
    if flags['alt']:
        # There may be a problem here with reading 32bit floats if
        # nb and nc are odd?
        dd += [('alt_dist', 'f', [], None),  # m
               ('alt_quality', 'H', [], None),
               ('alt_status', 'H', [], None)]
    if flags['ast']:
        dd += [('ast_dist', 'f', [], None),  # m
               ('ast_quality', 'H', [], None),
               ('ast_offset_time', 'h', [], LinFunc(0.0001)),  # seconds
               ('ast_pressure', 'f', [], None),  # dbar
               # This use of 'x' here is a hack
               ('ast_spare', 'B7x', [], None)]
    if flags['alt_raw']:
        dd += [('altraw_nsamp', 'L', [], None),
               ('altraw_dist', 'H', [], LinFunc(0.0001)),  # m
               ('altraw_samp', 'h', [], None)]
    if flags['echo']:
        dd += [('echo', 'H', [nc], None)]
    if flags['ahrs']:
        dd += [('orientmat', 'f', [3, 3], None),
               # This use of 'x' here is a hack
               ('ahrs_spare', 'B15x', [], None),
               ('ahrs_gyro', 'f', [3], None)]  # degrees per second
    if flags['p_gd']:
        dd += [('percent_good', 'B', [nc], None)]  # percent
    if flags['std']:
        dd += [('std_pitch', 'h', [], LinFunc(0.01)),  # degrees
               ('std_roll', 'h', [], LinFunc(0.01)),  # degrees
               ('std_heading', 'h', [], LinFunc(0.01)),  # degrees
               ('std_press', 'h', [], LinFunc(0.1)),  # dbar
               # This use of 'x' here is a hack
               ('std_spare', 'H22x', [], None)]
    # Now join this with the _burst_hdr
    out = DataDef(
        zip(_burst_hdr._names,
            _burst_hdr._format,
            _burst_hdr._shape,
            _burst_hdr._sci_func) +
        dd)
    return out

"""
Note on "This use of 'x' is a hack": I'm afraid that using a larger
int size will give syncing problems (e.g. unpack('HB')
vs. unpack('BH')), and I need to read SOMETHING otherwise, the
unpack order will get messed up. In the future, it'd be good to read
the size of the format, and hold that differently than self._N
(e.g. self._N2?)
"""
