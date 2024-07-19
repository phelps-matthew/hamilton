from hamilton.base.config import MessageNodeConfig, Exchange, Binding, Publishing


class AstrodynamicsControllerConfig(MessageNodeConfig):
    name = "AstrodynamicsController"
    exchanges = [
        Exchange(name="astrodynamics", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="astrodynamics", routing_keys=["observatory.astrodynamics.command.*"]),
    ]
    publishings = [
        Publishing(
            exchange="astrodynamics",
            routing_keys=[
                "observatory.astrodynamics.telemetry.kinematic_state",
                "observatory.astrodynamics.telemetry.aos_los",
                "observatory.astrodynamics.telemetry.interpolated_orbit",
                "observatory.astrodynamics.telemetry.all_aos_los",
                "observatory.astrodynamics.telemetry.tle",
            ],
        ),
    ]

    # RME
    LATTITUDE = 20.7464000000
    LONGITUDE = -156.4314700000
    ALTITUDE = 103.8000000000  # (meters)

    # Constraints
    MIN_ELEVATION = 10  # (degrees)


class AstrodynamicsClientConfig(MessageNodeConfig):
    name = "AstrodynamicsClient"
    exchanges = [
        Exchange(name="astrodynamics", type="topic", durable=True, auto_delete=False),
    ]
    bindings = [
        Binding(exchange="astrodynamics", routing_keys=["observatory.astrodynamics.telemetry.#"]),
    ]
    publishings = [
        Publishing(
            exchange="astrodynamics",
            routing_keys=[
                "observatory.astrodynamics.command.get_kinematic_state",
                "observatory.astrodynamics.command.get_aos_los",
                "observatory.astrodynamics.command.get_interpolated_orbit",
                "observatory.astrodynamics.command.recompute_all_orbits",
                "observatory.astrodynamics.command.get_all_aos_los",
                "observatory.astrodynamics.command.get_tle"
            ],
        ),
    ]
