from datetime import datetime, timedelta
from typing import Generator

from astral import LocationInfo
from astral.sun import elevation, azimuth

# internal imports
from fronius_aux import (
    Math,
    air_mass,
    direct_radiation_on_tilted_surface,
    SOLAR_CONSTANT
)


class SunInflux(object):

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
            # apparently the timezone imposes no effect on the computation of
            # astral.sun.elevation and azimuth
            timezone=parameter['location']['timezone']
        )
        self.debug = debug  # not used to date

    def sun_parameter(
            self,
            dateandtime: datetime
    ) -> dict[datetime, dict[str, dict[str, float]]]:
        """
        Calculates the energy acquired by solar irradiation on earth's ground
        and PV pnanels, in units of W * m**-2 and W at dateandtime [UTC]
        Latter being calculated from the configuration of each panel group
        :param dateandtime:
        :return: solar data
        """
        result = {
            dateandtime: {
                "sun": {
                    "power": 0.
                },
                "panels": {
                    "direct": 0.,
                    "diffuse": 0.
                }
            }
        }
        # diffuse sunlight on all panels
        for _, value in self.parameter['housetop'].items():
            result[dateandtime]['panels']['diffuse'] += (
                    value['area']['value']
                    * value['efficiency']['value']
                    * (1. + Math.cosdeg(value['inclination']['value'])) * 0.5)
        # sun elevation
        el = elevation(observer=self.location.observer,
                       dateandtime=dateandtime,
                       with_refraction=True)
        if el > 0:
            altitude = self.parameter["location"]["altitude"]["value"]
            # sun azimuth
            az = azimuth(observer=self.location.observer,
                         dateandtime=dateandtime)
            air_mass_attenuation, _ = air_mass(
                elevation=el,
                altitude=altitude)
            result[dateandtime]['sun']['elevation'] = el
            result[dateandtime]['sun']['azimuth'] = az
            result[dateandtime]['sun']['air_mass_attenuation'] = air_mass_attenuation
            result[dateandtime]['sun']['power'] = (SOLAR_CONSTANT
                                                   * Math.sindeg(el)
                                                   * air_mass_attenuation)
            # direct sunlight on all panels
            for _, value in self.parameter['housetop'].items():
                r = direct_radiation_on_tilted_surface(
                    elevation=el,
                    azimuth=az,
                    inclination=value['inclination']['value'],
                    orientation=value['orientation']['value'])
                result[dateandtime]['panels']['direct'] += (
                        SOLAR_CONSTANT
                        * air_mass_attenuation
                        * value['area']['value']
                        * value['efficiency']['value']
                        * r)

        return result

    @staticmethod
    def _date_generator(
            from_date: datetime,
            to_date: datetime = None,
            t_delta: int = 60
    ) -> Generator[datetime, None, None]:
        """
        Datetime generator increases by 1 hr
        :param from_date:
        :param to_date: may be empty if integration over one hour from from_date
        :param t_delta: time delta in minutes, must be equal time intervals
        between from_date and to_date
        :return: iterable
        """
        to_date = to_date if to_date else from_date + timedelta(hours=1)
        diff = (to_date - from_date).total_seconds() / 60
        assert diff % t_delta == 0, "Unequal intervals between from and to!"
        while from_date <= to_date:
            yield from_date
            from_date += timedelta(minutes=t_delta)

    @staticmethod
    def _mean_hours(
            p: list,
            t_delta: int = 60
    ) -> float:
        """
        Sum over means of all adjacent neighbors in list p
        :param p:
        :param t_delta: intervals in minutes
        :return: energy Wh
        """
        return (t_delta / 60 *
                sum([(p[i] + p[i + 1]) / 2 for i in range(len(p) - 1)]))

    def calc_modified(
            self,
            *,
            from_date: datetime,
            to_date: datetime = None
    ) -> tuple[float, ...]:
        """
        Integrates the energies over time defined by from_data and to_date
        :param from_date:
        :param to_date:
        :return:
        * accumulated energy on the ground in units of Wm⁻²
        * direct sunlight on the PV panels in units of Wh in the period
        from_date until to_date
        * diffuse sunlight on the (tilted) PV panels in units of hm²
        in the period from_date until to_date, to be multiplied by Wm⁻²
        """
        powers = list()
        panels = list()
        diffuse = list()
        t_delta: int = 12  # minutes

        for item in self._date_generator(from_date=from_date,
                                         to_date=to_date,
                                         t_delta=t_delta):
            res = self.sun_parameter(dateandtime=item)[item]
            powers.append(res['sun']['power'])
            panels.append(res['panels']['direct'])
            diffuse.append(res['panels']['diffuse'])

        if to_date:
            accumulated = self._mean_hours(
                p=powers,
                t_delta=t_delta)
            panels_all = self._mean_hours(
                p=panels,
                t_delta=t_delta)
            diffuse_all = self._mean_hours(
                p=diffuse,
                t_delta=t_delta)
        else:
            accumulated = powers[0]
            panels_all = panels[0]
            diffuse_all = diffuse[0]

        return (accumulated,
                panels_all,
                diffuse_all)
