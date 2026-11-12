# Offline conceptual car fixture

`basic_car.fs` builds eight independent bodies in one Part Studio: a chassis, a body, two axles, and four wheels. It uses editable FSGen variables for length, width, body height, wheelbase, wheel radius, wheel thickness, and axle radius. It is a non-roadgoing geometry fixture, not an assembly or driveline design.

With the pinned FSGen environment, `python -m h2cad validate fixtures/car/basic_car.fs` passed local OpenCascade validation: eight parts, 525414.5098 mm³, bounding box `[-57, -90, 1]` to `[57, 90, 65]` mm, no warnings. `tests/test_car_fixture.py` builds a 42 mm body-height variant from the 37 mm base: eight parts remain, volume increases by 48000 mm³, and the planner emits only the `#bodyHeight` variable update while preserving all other feature definitions. The focused two-test suite passed.

The planner currently treats a wheelbase variable change as a structural sketch edit and rejects it for explicit migration. This fixture does not establish live Onshape regeneration, assembly instances, native bridge creation, or human editability; those levels remain `not_run`.
