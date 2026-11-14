"""RPRR concept sizing, SI units; no CAD/network writes. Run with Python 3.11+."""
import json
import math
from pathlib import Path
from kinematics import inverse_aligned

G = 9.81
L1, L2, TOOL = .220, .160, .020
# name, estimated mass kg, proximal/distal/tool distances m.
# Motor masses are published; fabricated component masses are budgets.
ITEMS = [
    ('link1_2020', .110, .110, 0, 0),
    ('elbow_motor', .390, .150, 0, 0),
    ('elbow_bearings_shaft_plates_pulley', .220, .220, 0, 0),
    ('link2_2020', .080, .220, .080, 0),
    ('wrist_motor', .390, .220, .090, 0),
    ('wrist_bearings_shaft_plates_pulley', .150, .220, .160, 0),
    ('tool', .100, .220, .160, .020),
    ('payload', .200, .220, .160, .020),
    ('link_brackets_fasteners', .350, .180, 0, 0),
    ('moving_cable', .100, .220, .040, 0),
]
MASS_FACTOR = 1.25  # applies even to specified payload; conservative sizing reserve
OMEGA = [.5, .5, .5]  # joint rad/s, simultaneous operation permitted
ALPHA = [.5, .5, .5]  # joint rad/s2

def acceleration_bound(lengths):
    # Triangle bound on Cartesian acceleration of a serial planar chain.
    # Includes tangential and centripetal terms, without cancelling vectors.
    return sum(length * (sum(ALPHA[:j+1]) + sum(OMEGA[:j+1])**2)
               for j, length in enumerate(lengths))

def main():
    mass = sum(i[1] for i in ITEMS)
    moment = MASS_FACTOR * sum(m*G*(a+b+c) for _,m,a,b,c in ITEMS)
    torques = []
    for j, friction in enumerate([.05,.03,.01]):
        torque = sum(MASS_FACTOR*m*sum((a,b,c)[j:])*acceleration_bound((a,b,c))
                     for _,m,a,b,c in ITEMS)
        # Extra rotating mast/slide inertia budget; no centripetal torque about own axis.
        if j == 0: torque += .080*ALPHA[0]
        torques.append(2*(torque+friction))  # factor 2 beyond mass reserve
    ratios=[5,4,3]
    motor_torques=[t/(r*.9) for t,r in zip(torques,ratios)]
    lift_mass=MASS_FACTOR*(mass+.600)
    lift_force=lift_mass*(G+.1)+5 # 5 N guide/nut friction allowance
    lift_torque=lift_force*.002/(2*math.pi*.20*.9)
    # Continuous straight 2020 beam approximation; joints excluded.
    EI=69e9*7420e-12
    beam_defl=sum(MASS_FACTOR*m*G*(a+b+c)**2*(3*.4-(a+b+c))/(6*EI)
                  for _,m,a,b,c in ITEMS)
    mast_EI=4*EI  # four posts, conservatively no composite-section credit
    mast_theta=moment*.450/mast_EI
    mast_tip=moment*.450**2/(2*mast_EI)
    points=[]
    # With wrist offset aligned with link 2, effective second link is .180 m.
    for x,y in [(.4,0),(.3,-.2),(.3,0),(.3,.2)]:
        q1, _, q2, _ = inverse_aligned(x*1000, y*1000, 0)
        points.append(dict(x_mm=x*1000,y_mm=y*1000,base_deg=math.degrees(q1),elbow_deg=math.degrees(q2),wrist_deg=0))
    belts=[]
    for axis,n,c in [('base',100,.080),('elbow',80,.070),('wrist',60,.065)]:
        r1=20*.002/(2*math.pi); r2=n*.002/(2*math.pi)
        wrap=math.pi-2*math.asin((r2-r1)/c)
        idx=['base','elbow','wrist'].index(axis)
        belts.append(dict(axis=axis,teeth=[20,n],center_nominal_mm=c*1000,
                          pitch_length_mm=(2*c+math.pi*(r1+r2)+(r2-r1)**2/c)*1000,
                          small_wrap_deg=math.degrees(wrap),engaged_teeth=20*wrap/(2*math.pi),
                          design_tension_difference_N=torques[idx]/r2))
    result=dict(status='analytical concept; hardware and CAD acceptance outstanding',
        mass_items=[dict(name=n,kg=m,segments_m=[a,b,c]) for n,m,a,b,c in ITEMS],
        mass_reserve_factor=MASS_FACTOR,arm_mass_with_payload_kg=mass,
        lift_design_mass_kg=lift_mass,gravity_moment_Nm=moment,
        rotary_factored_output_torques_Nm=torques,motor_required_Nm=motor_torques,
        motor_design_available_Nm=.25,motor_margin=[.25/t for t in motor_torques],
        motor_max_rpm=[w*r*60/(2*math.pi) for w,r in zip(OMEGA,ratios)],
        lift_force_N=lift_force,lift_motor_required_Nm=lift_torque,
        lift_motor_rpm=5/2*60,lift_dynamic_margin=.25/lift_torque,
        brake_backdrive_ideal_Nm=lift_mass*G*.002/(2*math.pi),
        brake_static_margin=.25/(lift_mass*G*.002/(2*math.pi)),
        rail_couple_per_block_N=moment/(2*.100),
        base_bearing_couple_N=moment/.060,elbow_bearing_upper_bound_N=moment/.035,
        beam_only_tip_deflection_mm=beam_defl*1000,
        mast_rotation_tip_effect_mm=mast_theta*.4*1000,
        mast_translation_mm=mast_tip*1000,
        extrusion_bending_stress_MPa=moment*.010/7420e-12/1e6,
        belts=belts,workspace_points=points)
    assert max(motor_torques)<.25 and lift_torque<.25
    assert all(b['engaged_teeth']>6 for b in belts)
    out=Path(__file__).resolve().parents[2]/'artifacts'/'robot'
    out.mkdir(parents=True,exist_ok=True)
    (out/'calculations.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('mass_items','belts')},indent=2))

if __name__=='__main__': main()
