import math
from datetime import datetime, timedelta
from astral.sun import elevation, azimuth
from astral import LocationInfo
from typing import Generator


class SunInflux(object):
    SOLAR_CONSTANT = 1_361  # W m⁻²
    A = 0.00014  # constant / m⁻¹

    def __init__(
            self,
            *,
            parameter: dict,
            debug: bool = False
    ):
        """
        Define location info
        All times in UTC
        :param parameter:
        :param debug:
        """
        self.parameter = parameter
        self.location = LocationInfo(
            name=parameter['location']['city'],
            region=parameter['location']['region'],
            latitude=parameter['location']['latitude'],
            longitude=parameter['location']['longitude'],
            timezone=parameter['location']['timezone']
        )
        self.debug = debug  # not used

    def sun_parameter(
            self,
            dateandtime: datetime
    ) -> dict[str, dict[str, float]]:
        """
        Calculates the energy acquired by solar irradiation on earth's ground
        and PV pnanels, in units of W * m**-2 and W.
        Latter being calculated from the configuration of each panel group
        :param dateandtime:
        :return: solar data
        """
        el = elevation(observer=self.location.observer,
                       dateandtime=dateandtime,
                       with_refraction=True)
        if el > 0:
            altitude = self.parameter["location"]["altitude"]["value"]
            az = azimuth(observer=self.location.observer,
                         dateandtime=dateandtime)

            air_mass_revised = 1. / (
                    math.cos(math.radians(90. - el))
                    + 0.50572 * (6.07995 + el) ** -1.6364
            )
            air_mass_attenuation = (
                    (1. - self.A * altitude) * 0.7 ** air_mass_revised ** 0.678
                    + self.A * altitude
            )

            result = {
                dateandtime: {
                    "sun": {
                        "elevation": el,
                        "azimuth": az,
                        "power": (self.SOLAR_CONSTANT
                                  * math.sin(math.radians(el))
                                  * air_mass_attenuation),  # ToDo: air mass to be considered?
                                  # * 1.),
                        "air_mass_attenuation": air_mass_attenuation
                    },
                    "panel": {}
                }
            }

            for item, value in self.parameter['housetop'].items():
                # https://www.pveducation.org/pvcdrom/properties-of-sunlight/arbitrary-orientation-and-tilt
                r = max(
                    math.cos(math.radians(el))
                    * math.sin(math.radians(value['inclination']['value']))
                    * math.cos(math.radians(value['orientation']['value'] - az))
                    + math.sin(math.radians(el))
                    * math.cos(math.radians(value['inclination']['value'])),
                    0.
                )
                # incidence_angle_sun = math.degrees(math.asin(r))
                result[dateandtime]["panel"][item] = (
                        self.SOLAR_CONSTANT
                        * air_mass_attenuation
                        * value['area']['value']
                        * value['efficiency']['value']
                        * r
                )
            return result

        else:
            return {
                dateandtime: {
                    "sun": {
                        "power": 0.
                    },
                    "panel": {}
                }
            }

    @staticmethod
    def _date_generator(
            from_date: datetime,
            to_date: datetime = None,
            t_delta: int = 60
    ) -> Generator[datetime, None, None]:
        """
        Datetime generator increases by 1 hr
        :param from_date:
        :param to_date:
        :param t_delta: time delta in minutes
        :return: iterable
        """
        to_date = to_date if to_date else from_date
        while from_date <= to_date:
            yield from_date
            from_date = from_date + timedelta(minutes=t_delta)

    @staticmethod
    def _mean_hours(p: list) -> float:
        """
        Sum over means of all adjacent neighbors in list p
        :param p:
        :return:
        """
        return sum(
            [(p[i] + p[i + 1]) / 2 for i in range(len(p) - 1)]
        )

    def calc(
            self,
            *,
            from_date: datetime,
            to_date: datetime = None
    ) -> tuple[float, float]:
        """
        Integrates the energies over time defined by from_data and to_date
        :param from_date:
        :param to_date: may be empty if integration over one hour from from_date
        :return:
        """
        res: dict = dict()
        panels: dict = dict()
        panels_all: float = 0.

        for item in self._date_generator(
                from_date=from_date,
                to_date=to_date
        ):
            res.update(self.sun_parameter(dateandtime=item))

        for item in res.values():
            for k, v in item['panel'].items():
                try:
                    panels[k].append(v)
                except KeyError:
                    panels[k] = [v]

        powers = [v['sun']['power'] for v in res.values()]
        if to_date:
            accumulated = self._mean_hours(powers)
            for v in panels.values():
                panels_all += self._mean_hours(v)
        else:
            accumulated = powers[0]
            for v in panels.values():
                panels_all += v[0]

        return accumulated * 3_600, panels_all / 1_000
