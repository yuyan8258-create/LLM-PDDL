(define (problem gearbox-easy)
  (:domain image_gearbox_assembly)

  (:objects
    gearbox-housing input-shaft countershaft input-bearing-carrier - permanent-component
  )

  (:init
    (precedes gearbox-housing input-shaft)
    (precedes input-shaft countershaft)
    (precedes countershaft input-bearing-carrier)
    (has-predecessor countershaft)
    (has-predecessor input-bearing-carrier)
    (has-predecessor input-shaft)
  )

  (:goal
    (and
      (assembled gearbox-housing)
      (assembled input-shaft)
      (assembled countershaft)
      (assembled input-bearing-carrier)
    )
  )
)
