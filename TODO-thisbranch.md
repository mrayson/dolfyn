
- Create orientmat for all instruments (in/after read functions)
  - Should we drop heading/pitch/roll, and let user calculate these if
    needed?
  - Do we give the user the choice to keep raw (instrument
    manufacturer defined) heading/pitch/roll?
- Document ``dat.set_declination``
- Remove ``declination_in_orientmat`` and similar variables
- Remove ``_check_declination`` function?
- enforce no setting of dat.props['declination']?
- Handle userdata.json declination specification (``declin = info.pop('declination')``, then do ``set_declination(declin)``)
- Tests:
  - test for consistency of ``orient2euler`` and ``euler2orient``
  - update data files to match new API rules (e..g, heading, pitch, roll defs)
- Give users the option (in ``dolfyn.read``) to keep the raw instrument orientation data in ``orient.raw`` +doc this
- Move `Velocity.calc_principle_angle` to a function in the API (`dolfyn.calc_principal_angle`)
- Use degrees, instead of radians, for principal angle?