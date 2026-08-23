(define (problem gearbox-adl-smoke-problem)

  (:domain gearbox-adl-smoke)

  (:objects
    p1 p2 - permanent-component
    t1    - temporary-aid
  )

  (:init
    (precedes p1 p2)
    (requires-aid p2 t1)
  )

  (:goal
    (and
      (assembled p1)
      (assembled p2)
      (not (aid-present t1))
    )
  )
)