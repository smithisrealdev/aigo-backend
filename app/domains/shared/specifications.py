"""Specification Pattern for complex queries.

This module implements the Specification pattern for building
complex, reusable query conditions.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from sqlalchemy import and_, not_, or_

from app.infra.database import Base

T = TypeVar("T", bound=Base)


class Specification(ABC, Generic[T]):
    """Abstract base class for specifications.

    Specifications encapsulate query conditions in reusable,
    composable objects following the Specification pattern.

    Example:
        class ActiveUserSpec(Specification[User]):
            def to_expression(self):
                return User.is_active == True

        class PremiumUserSpec(Specification[User]):
            def to_expression(self):
                return User.subscription_type == "premium"

        # Combine specifications
        active_premium = ActiveUserSpec() & PremiumUserSpec()
        users = await repo.find_many(active_premium.to_expression())
    """

    @abstractmethod
    def to_expression(self) -> Any:
        """Convert specification to SQLAlchemy expression."""
        ...

    def __and__(self, other: "Specification[T]") -> "AndSpecification[T]":
        """Combine with AND."""
        return AndSpecification(self, other)

    def __or__(self, other: "Specification[T]") -> "OrSpecification[T]":
        """Combine with OR."""
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification[T]":
        """Negate the specification."""
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    """Combines two specifications with AND."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def to_expression(self) -> Any:
        """Return AND of both specifications."""
        return and_(self.left.to_expression(), self.right.to_expression())


class OrSpecification(Specification[T]):
    """Combines two specifications with OR."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def to_expression(self) -> Any:
        """Return OR of both specifications."""
        return or_(self.left.to_expression(), self.right.to_expression())


class NotSpecification(Specification[T]):
    """Negates a specification."""

    def __init__(self, spec: Specification[T]) -> None:
        self.spec = spec

    def to_expression(self) -> Any:
        """Return negation of the specification."""
        return not_(self.spec.to_expression())


class TrueSpecification(Specification[T]):
    """A specification that always returns True."""

    def to_expression(self) -> Any:
        """Return a condition that is always true."""
        return True


class FalseSpecification(Specification[T]):
    """A specification that always returns False."""

    def to_expression(self) -> Any:
        """Return a condition that is always false."""
        return False
