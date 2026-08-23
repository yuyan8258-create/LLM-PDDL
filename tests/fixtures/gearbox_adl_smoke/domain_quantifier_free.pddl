(define (domain gearbox-qf-smoke)

  (:requirements
    :strips
    :typing
    :negative-preconditions
  )

  (:types
    permanent-component
    temporary-aid
  )

  (:predicates

    ;; -------------------------
    ;; Semantic predicates
    ;; -------------------------

    (assembled
      ?p - permanent-component
    )

    (aid-present
      ?t - temporary-aid
    )

    (precedes
      ?pred - permanent-component
      ?p    - permanent-component
    )

    (requires-aid
      ?p - permanent-component
      ?t - temporary-aid
    )


    ;; -------------------------
    ;; Encoding-only metadata
    ;; -------------------------

    (has-predecessor
      ?p - permanent-component
    )

    (has-aid-requirement
      ?p - permanent-component
    )

    (withdraw-group-1
      ?t - temporary-aid
      ?p - permanent-component
    )

    (withdraw-group-2
      ?t  - temporary-aid
      ?p1 - permanent-component
      ?p2 - permanent-component
    )
  )


  ;; =========================================================
  ;; Permanent component assembly
  ;; =========================================================

  (:action assemble-basic
    :parameters (
      ?p - permanent-component
    )

    :precondition
      (and
        (not (assembled ?p))
        (not (has-predecessor ?p))
        (not (has-aid-requirement ?p))
      )

    :effect
      (assembled ?p)
  )


  (:action assemble-after
    :parameters (
      ?p    - permanent-component
      ?pred - permanent-component
    )

    :precondition
      (and
        (not (assembled ?p))

        (has-predecessor ?p)
        (not (has-aid-requirement ?p))

        (precedes ?pred ?p)
        (assembled ?pred)
      )

    :effect
      (assembled ?p)
  )


  (:action assemble-with-aid
    :parameters (
      ?p - permanent-component
      ?t - temporary-aid
    )

    :precondition
      (and
        (not (assembled ?p))

        (not (has-predecessor ?p))
        (has-aid-requirement ?p)

        (requires-aid ?p ?t)
        (aid-present ?t)
      )

    :effect
      (assembled ?p)
  )


  (:action assemble-after-with-aid
    :parameters (
      ?p    - permanent-component
      ?pred - permanent-component
      ?t    - temporary-aid
    )

    :precondition
      (and
        (not (assembled ?p))

        (has-predecessor ?p)
        (has-aid-requirement ?p)

        (precedes ?pred ?p)
        (assembled ?pred)

        (requires-aid ?p ?t)
        (aid-present ?t)
      )

    :effect
      (assembled ?p)
  )


  ;; =========================================================
  ;; Temporary aid
  ;; =========================================================

  (:action insert-aid
    :parameters (
      ?t - temporary-aid
    )

    :precondition
      (not (aid-present ?t))

    :effect
      (aid-present ?t)
  )


  (:action withdraw-aid-after-one
    :parameters (
      ?t - temporary-aid
      ?p - permanent-component
    )

    :precondition
      (and
        (aid-present ?t)

        (withdraw-group-1 ?t ?p)

        (requires-aid ?p ?t)
        (assembled ?p)
      )

    :effect
      (not (aid-present ?t))
  )


  (:action withdraw-aid-after-two
    :parameters (
      ?t  - temporary-aid
      ?p1 - permanent-component
      ?p2 - permanent-component
    )

    :precondition
      (and
        (aid-present ?t)

        (withdraw-group-2 ?t ?p1 ?p2)

        (requires-aid ?p1 ?t)
        (requires-aid ?p2 ?t)

        (assembled ?p1)
        (assembled ?p2)
      )

    :effect
      (not (aid-present ?t))
  )
)