"""PV name parser for ESS EPICS naming convention (ESS-0000757).

Parses PV strings into structured components and validates format.
Supports all 4 valid ESS PV formats:
  1. Sys-Sub:Dis-Dev-Idx:Property   (full device PV with subsystem)
  2. Sys:Dis-Dev-Idx:Property       (device PV without subsystem)
  3. Sys-Sub::Property              (high-level system PV with subsystem)
  4. Sys::Property                  (high-level system PV)
"""

import re
from dataclasses import dataclass
from typing import List, Optional

__all__ = ["PVComponents", "parse_pv", "is_valid_format"]


# Format type constants
FMT_FULL = "full"                      # Sys-Sub:Dis-Dev-Idx:Property
FMT_NO_SUBSYSTEM = "no-subsystem"      # Sys:Dis-Dev-Idx:Property
FMT_HIGH_LEVEL_SUBSYS = "high-level-subsys"  # Sys-Sub::Property
FMT_HIGH_LEVEL_SYS = "high-level-sys"  # Sys::Property


@dataclass
class PVComponents:
    """Parsed PV name decomposed into ESS naming convention elements.

    Attributes:
        system: System mnemonic (e.g., 'DTL', 'ISrc', 'PBI')
        subsystem: Subsystem mnemonic, empty string if not present
        discipline: Discipline mnemonic (e.g., 'EMR', 'WtrC', 'Ctrl')
        device: Device type mnemonic (e.g., 'TT', 'PT', 'MTCA')
        index: Device instance index (e.g., '001', '01', '100')
        property: PV property (e.g., 'Temperature', 'Status', '#Debug')
        raw: Original PV string
        format_type: One of FMT_FULL, FMT_NO_SUBSYSTEM, FMT_HIGH_LEVEL_SUBSYS, FMT_HIGH_LEVEL_SYS
    """
    system: str
    subsystem: str
    discipline: str
    device: str
    index: str
    property: str
    raw: str
    format_type: str

    @property  # type: ignore[override]
    def ess_name(self) -> str:
        """The ESS Name portion (without property).

        Returns the device name or system/subsystem for high-level PVs.
        """
        if self.format_type == FMT_FULL:
            return f"{self.system}-{self.subsystem}:{self.discipline}-{self.device}-{self.index}"
        elif self.format_type == FMT_NO_SUBSYSTEM:
            return f"{self.system}:{self.discipline}-{self.device}-{self.index}"
        elif self.format_type == FMT_HIGH_LEVEL_SUBSYS:
            return f"{self.system}-{self.subsystem}"
        else:  # FMT_HIGH_LEVEL_SYS
            return self.system

    @property  # type: ignore[override]
    def is_high_level(self) -> bool:
        """True if this is a high-level system PV (no device part)."""
        return self.format_type in (FMT_HIGH_LEVEL_SYS, FMT_HIGH_LEVEL_SUBSYS)

    @property  # type: ignore[override]
    def is_internal(self) -> bool:
        """True if property starts with # (internal PV)."""
        return self.property.startswith("#")

    def to_list(self) -> List[str]:
        """Return [sys, sub, dis, dev, idx, prop] for backwards compatibility."""
        return [self.system, self.subsystem, self.discipline,
                self.device, self.index, self.property]


def parse_pv(pv: str) -> Optional[PVComponents]:
    """Parse a PV string into its components.

    Args:
        pv: Full PV name string (e.g., 'DTL-010:EMR-TT-001:Temperature')

    Returns:
        PVComponents if the format is valid, None if invalid.
    """
    if not pv or not isinstance(pv, str):
        return None

    parts = pv.split(":")

    # Must have exactly 3 colon-separated segments
    # (system-part, device-part, property)
    if len(parts) != 3:
        return None

    sys_part, dev_part, prop = parts

    # Property must exist
    if not prop:
        return None

    # System part must exist
    if not sys_part:
        return None

    # Parse system part (Sys or Sys-Sub)
    system, subsystem = _parse_system_part(sys_part)
    if system is None:
        return None

    # High-level PV: empty device part (double colon ::)
    if dev_part == "":
        fmt = FMT_HIGH_LEVEL_SUBSYS if subsystem else FMT_HIGH_LEVEL_SYS
        return PVComponents(
            system=system,
            subsystem=subsystem,
            discipline="",
            device="",
            index="",
            property=prop,
            raw=pv,
            format_type=fmt,
        )

    # Device PV: parse Dis-Dev-Idx
    discipline, device, index = _parse_device_part(dev_part)
    if discipline is None:
        return None

    fmt = FMT_FULL if subsystem else FMT_NO_SUBSYSTEM
    return PVComponents(
        system=system,
        subsystem=subsystem,
        discipline=discipline,
        device=device,
        index=index,
        property=prop,
        raw=pv,
        format_type=fmt,
    )


def _parse_system_part(sys_part: str) -> tuple:
    """Parse 'Sys' or 'Sys-Sub' into (system, subsystem).

    Returns (system, subsystem) or (None, None) if invalid.
    """
    if "-" in sys_part:
        idx = sys_part.index("-")
        system = sys_part[:idx]
        subsystem = sys_part[idx + 1:]
        if not system or not subsystem:
            return None, None
        return system, subsystem
    else:
        return sys_part, ""


def _parse_device_part(dev_part: str) -> tuple:
    """Parse 'Dis-Dev-Idx' into (discipline, device, index).

    Returns (discipline, device, index) or (None, None, None) if invalid.
    """
    segments = dev_part.split("-")
    if len(segments) < 3:
        return None, None, None

    discipline = segments[0]
    device = segments[1]
    # Index may contain dashes (e.g., P&ID redundancy: '002a')
    # Rejoin remaining segments as index
    index = "-".join(segments[2:])

    if not discipline or not device:
        return None, None, None

    return discipline, device, index


def is_valid_format(pv: str) -> bool:
    """Check if a PV string has a valid ESS naming convention format.

    Args:
        pv: Full PV name string

    Returns:
        True if the format matches one of the 4 valid ESS formats.
    """
    return parse_pv(pv) is not None
