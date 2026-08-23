(define (domain gearbox-adl-precedence-only)

  (:requirements :adl :typing)

  (:types
    permanent-component
  )

  (:predicates
    (assembled ?p - permanent-component)
    (precedes
      ?before - permanent-component
      ?after  - permanent-component
    )
  )

  (:action assemble
    :parameters (?p - permanent-component)

    :precondition
      (and
        (not (assembled ?p))

        (forall (?pred - permanent-component)
          (imply
            (precedes ?pred ?p)
            (assembled ?pred)
          )
        )
      )

    :effect
      (assembled ?p)
  )
)