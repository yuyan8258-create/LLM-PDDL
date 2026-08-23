(define (problem gearbox-qf-medium-smoke)

  (:domain gearbox-qf-smoke)

  (:objects
    p1 p2 - permanent-component
    t1    - temporary-aid
  )

  (:init

    ;; Semantic dependency
    (precedes p1 p2)
    (requires-aid p2 t1)

    ;; Automatically derived encoding metadata
    (has-predecessor p2)
    (has-aid-requirement p2)

    (withdraw-group-1 t1 p2)
  )

  (:goal
    (and
      (assembled p1)
      (assembled p2)
      (not (aid-present t1))
    )
  )
)