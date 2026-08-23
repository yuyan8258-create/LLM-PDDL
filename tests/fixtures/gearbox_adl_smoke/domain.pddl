(define (domain gearbox-adl-smoke)

  (:requirements
    :typing
    :negative-preconditions
    :universal-preconditions
  )

  (:types
    permanent-component
    temporary-aid
  )

  (:predicates
    (assembled ?p - permanent-component)
    (aid-present ?t - temporary-aid)

    (precedes
      ?before - permanent-component
      ?after  - permanent-component
    )

    (requires-aid
      ?p - permanent-component
      ?t - temporary-aid
    )
  )


  (:action assemble
    :parameters (
      ?p - permanent-component
    )

    :precondition
      (and
        (not (assembled ?p))

        (forall (?pred - permanent-component)
          (or
            (not (precedes ?pred ?p))
            (assembled ?pred)
          )
        )

        (forall (?t - temporary-aid)
          (or
            (not (requires-aid ?p ?t))
            (aid-present ?t)
          )
        )
      )

    :effect
      (assembled ?p)
  )


  (:action insert-aid
    :parameters (
      ?t - temporary-aid
    )

    :precondition
      (not (aid-present ?t))

    :effect
      (aid-present ?t)
  )


  (:action withdraw-aid
    :parameters (
      ?t - temporary-aid
    )

    :precondition
      (and
        (aid-present ?t)

        (forall (?p - permanent-component)
          (or
            (not (requires-aid ?p ?t))
            (assembled ?p)
          )
        )
      )

    :effect
      (not (aid-present ?t))
  )
)