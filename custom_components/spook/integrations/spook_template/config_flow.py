"""Spook - Not your homie."""
from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_STATE_TEMPLATE,
    CONF_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfApparentPower,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfInformation,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfVolumetricFlux,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import DOMAIN, PLATFORMS

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping


def generate_schema(domain: str) -> dict[vol.Marker, Any]:
    """Generate schema."""
    schema = {
        vol.Required(CONF_STATE_TEMPLATE): selector.TemplateSelector(),
    }

    if domain == Platform.SENSOR:
        schema |= {
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        "none",
                        *sorted(
                            {
                                cls.value
                                for unit in (
                                    UnitOfApparentPower,
                                    UnitOfEnergy,
                                    UnitOfLength,
                                    UnitOfApparentPower,
                                    UnitOfElectricCurrent,
                                    UnitOfElectricPotential,
                                    UnitOfFrequency,
                                    UnitOfPower,
                                    UnitOfTemperature,
                                    UnitOfInformation,
                                    UnitOfIrradiance,
                                    UnitOfMass,
                                    UnitOfDataRate,
                                    UnitOfPressure,
                                    UnitOfPrecipitationDepth,
                                    UnitOfSoundPressure,
                                    UnitOfSpeed,
                                    UnitOfTime,
                                    UnitOfVolume,
                                    UnitOfVolumeFlowRate,
                                    UnitOfVolumetricFlux,
                                )
                                for cls in unit
                            },
                            key=str.casefold,
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="unit_of_measurement",
                    custom_value=True,
                ),
            ),
            vol.Optional(CONF_DEVICE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        "none",
                        *sorted(
                            [
                                cls.value
                                for cls in SensorDeviceClass
                                if cls != SensorDeviceClass.ENUM
                            ],
                            key=str.casefold,
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="device_class",
                ),
            ),
            vol.Optional(CONF_STATE_CLASS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["none", *sorted([cls.value for cls in SensorStateClass])],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="state_class",
                ),
            ),
        }

    return schema


async def options_schema(domain: str, _: SchemaCommonFlowHandler) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(generate_schema(domain))


def config_schema(domain: str) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
        }
        | generate_schema(domain),
    )


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to template_type."""
    return cast(str, options["template_type"])


def set_template_type(
    template_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Set template type."""

    async def _set_template_type(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add template type to user input."""
        return {"template_type": template_type, **user_input}

    return _set_template_type


CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(PLATFORMS),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        config_schema(Platform.BINARY_SENSOR),
        validate_user_input=set_template_type(Platform.BINARY_SENSOR),
    ),
    Platform.SENSOR: SchemaFlowFormStep(
        config_schema(Platform.SENSOR),
        validate_user_input=set_template_type(Platform.SENSOR),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        partial(options_schema, Platform.BINARY_SENSOR),
    ),
    Platform.SENSOR: SchemaFlowFormStep(partial(options_schema, Platform.SENSOR)),
}


class SpookTemplateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for Spook template helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""
