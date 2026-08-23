(define (problem gearbox-qf-hard-smoke)

  (:domain gearbox-qf-smoke)

  (:objects
    p1 p2 p3 - permanent-component
    t1       - temporary-aid
  )

  (:init

    ;; -------------------------------------------------
    ;; Semantic relations
    ;; -------------------------------------------------

    (precedes p1 p2)

    (requires-aid p2 t1)
    (requires-aid p3 t1)


    ;; -------------------------------------------------
    ;; Automatically derived encoding metadata
    ;; -------------------------------------------------

    (has-predecessor p2)

    (has-aid-requirement p2)
    (has-aid-requirement p3)

    (withdraw-group-2 t1 p2 p3)
  )

  (:goal
    (and
      (assembled p1)
      (assembled p2)
      (assembled p3)

      (not (aid-present t1))
    )
  )
)