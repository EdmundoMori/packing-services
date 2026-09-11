"""Packing online generalizable: bucle de decisión con presupuesto de información.

Ejes (no mezclarlos):

- Qué se decide: pose / contenedor (este paquete).
- Qué se ve: ventana ``observe_p``.
- Qué se puede hacer: elegir entre los primeros ``select_s``; commit irrevocable.

``packing_mode=offline`` no entra aquí. La política aprendida se enchufa
como ``PlacementPolicy`` sobre el mismo bucle (``drl_policy_3d_bpp``).

Importar submódulos concretos (``online.loop``, ``online.learned.policy``)
para evitar ciclos con el registro de algoritmos.
"""

__all__ = ["InformationBudget", "run_online_loop"]
