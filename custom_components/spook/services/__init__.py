"""Spook - Not your homie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import Any, final, overload

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Service, ServiceCall, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.helpers.service import (
    SERVICE_DESCRIPTION_CACHE,
    _load_services_file,
    async_register_admin_service,
    async_set_service_schema,
)
from homeassistant.loader import async_get_integration

from ..const import DOMAIN, LOGGER


class AbstractSpookServiceBase(ABC):
    """Abstract base class to hold a Spook service."""

    hass: HomeAssistant
    domain: str
    service: str
    schema: dict[str | vol.Marker, Any] | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    @abstractmethod
    async def async_register(self) -> None:
        """Handle the service call."""
        raise NotImplementedError

    @final
    @callback
    def async_unregister(self) -> None:
        """Unregister the service from Home Assistant."""
        LOGGER.debug(
            "Unregistering Spook service: %s.%s",
            self.domain,
            self.service,
        )

        self.hass.services.async_remove(self.domain, self.service)

    @overload
    async def async_handle_service(self, entity: Entity, call: ServiceCall) -> None:
        ...

    @abstractmethod
    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        raise NotImplementedError


class ReplaceExistingService(AbstractSpookServiceBase):
    """This service replaces an existing service."""

    overriden_service: Service


class AbstractSpookService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook service."""

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        # Only register the service if the domain is the spook integration
        # or if the target integration is loaded.
        if self.domain != DOMAIN and self.domain not in self.hass.config.components:
            LOGGER.debug(
                "Not registering Spook %s.%s service, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )

        LOGGER.debug(
            "Registering Spook service: %s.%s",
            self.domain,
            self.service,
        )

        self.hass.services.async_register(
            domain=self.domain,
            service=self.service,
            service_func=self.async_handle_service,
            schema=vol.Schema(self.schema),
        )


class AbstractSpookAdminService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook admin service."""

    @final
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant."""
        if self.domain != DOMAIN and self.domain not in self.hass.config.components:
            LOGGER.debug(
                "Not registering Spook %s.%s admin service, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )
            return False

        LOGGER.debug(
            "Registering Spook admin service: %s.%s",
            self.domain,
            self.service,
        )
        async_register_admin_service(
            hass=self.hass,
            domain=self.domain,
            service=self.service,
            service_func=self.async_handle_service,
            schema=vol.Schema(self.schema),
        )
        return True


class AbstractSpookEntityService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook entity service."""

    platform: str
    required_features: list[int] | None = None

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity service: %s.%s for platform %s",
            self.domain,
            self.service,
            self.platform,
        )

        if not (
            platform := next(
                platform
                for platform in self.hass.data[DATA_ENTITY_PLATFORM][self.domain]
                if platform.domain == self.platform
            )
        ):
            raise RuntimeError(
                f"Could not find platform {self.platform} for domain "
                f"{self.domain} to register service: "
                f"{self.domain}.{self.service}"
            )

        platform.async_register_entity_service(
            name=self.service,
            func=self.async_handle_service,
            schema=self.schema,
            required_features=self.required_features,
        )


class AbstractSpookEntityComponentService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook entity component service."""

    required_features: list[int] | None = None

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity component service: %s.%s",
            self.domain,
            self.service,
        )

        if self.domain not in self.hass.data[DATA_INSTANCES]:
            raise RuntimeError(
                f"Could not find entity component {self.domain} to register "
                f"service: {self.domain}.{self.service}"
            )

        component: EntityComponent[Entity] = self.hass.data[DATA_INSTANCES][self.domain]

        component.async_register_entity_service(
            name=self.service,
            func=self.async_handle_service,
            schema=self.schema,
            required_features=self.required_features,
        )


@dataclass
class SpookServiceManager:
    """Class to manage Spook services."""

    hass: HomeAssistant

    _services: set[AbstractSpookService] = field(default_factory=set)
    _service_schemas: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Post initialization."""
        LOGGER.debug("Spook service manager initialized")

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Set up the Spook services."""
        LOGGER.debug("Setting up Spook services")

        entry.async_on_unload(self.async_on_unload)
        integration = await async_get_integration(self.hass, DOMAIN)
        self._service_schemas = await self.hass.async_add_executor_job(  # type: ignore
            _load_services_file, self.hass, integration
        )

        # Load all services
        for module_file in Path(__file__).parent.rglob("*.py"):
            if module_file.name == "__init__.py":
                continue
            module = importlib.import_module(f".{module_file.name[:-3]}", __package__)
            service = module.SpookService(self.hass)

            if isinstance(
                service, ReplaceExistingService
            ) and self.hass.services.has_service(service.domain, service.service):
                LOGGER.debug(
                    "Unregistering service that will be overriden service: %s.%s",
                    service.domain,
                    service.service,
                )
                # pylint: disable=protected-access
                service.overriden_service = self.hass.services._services[
                    service.domain
                ].pop(service.service)

            await self.async_register_service(service)

    async def async_register_service(self, service: AbstractSpookService) -> None:
        """Register a Spook service."""
        service.async_register()
        self._services.add(service)

        # Override service description with Spook's if the service is not
        # for the Spook integration.
        if service.domain != DOMAIN and (
            service_schema := self._service_schemas.get(
                f"{service.domain}_{service.service}"
            )
        ):
            LOGGER.debug(
                "Injecting Spook service schema for: %s.%s",
                service.domain,
                service.service,
            )
            async_set_service_schema(
                self.hass,
                domain=service.domain,
                service=service.service,
                schema=service_schema,
            )

    @callback
    def async_on_unload(self) -> None:
        """Tear down the Spook services."""
        LOGGER.debug("Tearing down Spook services")
        for service in self._services:
            LOGGER.debug(
                "Unregistering service: %s.%s", service.domain, service.service
            )
            service.async_unregister()

            if isinstance(service, ReplaceExistingService):
                LOGGER.debug(
                    "Restoring service that was overriden previously: %s.%s",
                    service.domain,
                    service.service,
                )

                # pylint: disable-nect=protected-access
                self.hass.services._services.setdefault(service.domain, {})[
                    service.service
                ] = service.overriden_service

                # Flush service description schema cache
                self.hass.data.pop(SERVICE_DESCRIPTION_CACHE, None)
